"""In-process tests for server.py's module-level setup and main().

server.py configures everything at import time, so each test imports a fresh
copy under a controlled environment. The subprocess tests in
test_healthcheck.py cover the same module end to end, but coverage does not
see them.
"""

import importlib
import importlib.metadata
import logging
import sys
from unittest.mock import MagicMock

import dotenv
import pytest
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from fastmcp.server.middleware.rate_limiting import SlidingWindowRateLimitingMiddleware
from fastmcp.server.transforms.search import BM25SearchTransform
from fastmcp.server.transforms.search import RegexSearchTransform

from ghostfolio_mcp.models import TransportConfig

MODULE = "ghostfolio_mcp.server"

SERVER_ENV_VARS = (
    "GHOSTFOLIO_URL",
    "GHOSTFOLIO_TOKEN",
    "GHOSTFOLIO_VERIFY_SSL",
    "GHOSTFOLIO_TIMEOUT",
    "GHOSTFOLIO_DISABLED_TAGS",
    "READ_ONLY_MODE",
    "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_MAX_REQUESTS",
    "RATE_LIMIT_WINDOW_MINUTES",
    "TOOL_SEARCH_ENABLED",
    "TOOL_SEARCH_STRATEGY",
    "TOOL_SEARCH_MAX_RESULTS",
    "LOG_LEVEL",
    "MCP_TRANSPORT",
    "MCP_HTTP_HOST",
    "MCP_HTTP_PORT",
    "MCP_HTTP_BEARER_TOKEN",
    "OIDC_CONFIG_URL",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET",
    "OIDC_BASE_URL",
    "OIDC_REDIRECT_PATH",
    "OIDC_REQUIRED_SCOPES",
    "OIDC_ALLOWED_REDIRECT_URIS",
    "OIDC_VERIFY_ID_TOKEN",
    "OIDC_FORWARD_RESOURCE",
    "SENTRY_DSN",
)

OIDC_SETTINGS = {
    "oidc_config_url": "https://id.example.com/.well-known/openid-configuration",
    "oidc_client_id": "client-id",
    "oidc_client_secret": "client-secret",
    "oidc_base_url": "https://mcp.example.com",
}


@pytest.fixture
def load_server(monkeypatch):
    """Import a fresh server module with only the given environment."""
    for name in SERVER_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    # A developer's .env must not leak into the tests.
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *_args, **_kwargs: False)

    def factory(**env: str):
        env.setdefault("GHOSTFOLIO_URL", "https://ghostfolio.test:3333")
        env.setdefault("GHOSTFOLIO_TOKEN", "api-token")
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        sys.modules.pop(MODULE, None)
        module = importlib.import_module(MODULE)
        monkeypatch.setattr(module.mcp, "run", MagicMock())
        return module

    yield factory
    sys.modules.pop(MODULE, None)


async def tool_names(module) -> set[str]:
    return {tool.name for tool in await module.mcp.list_tools()}


@pytest.mark.asyncio
async def test_health_route_answers_ok(load_server):
    server = load_server()

    response = await server.health(MagicMock())

    assert response.status_code == 200
    assert response.body == b"ok"


@pytest.mark.asyncio
async def test_all_tools_are_exposed_by_default(load_server):
    names = await tool_names(load_server())

    assert {"get_accounts", "create_account", "delete_activity"} <= names
    assert "search_tools" not in names


@pytest.mark.asyncio
async def test_read_only_mode_hides_write_tools(load_server, caplog):
    caplog.set_level(logging.INFO)
    names = await tool_names(load_server(READ_ONLY_MODE="true"))

    assert {"get_accounts", "get_portfolio_details", "get_watchlist"} <= names
    assert not names & {
        "create_account",
        "update_activity",
        "delete_activity",
        "add_to_watchlist",
        "import_transactions",
    }
    assert "Read-only mode is enabled" in caplog.text


@pytest.mark.asyncio
async def test_disabled_tags_hide_matching_tools(load_server, caplog):
    caplog.set_level(logging.INFO)
    names = await tool_names(load_server(GHOSTFOLIO_DISABLED_TAGS="watchlist, export"))

    assert not names & {
        "get_watchlist",
        "add_to_watchlist",
        "remove_from_watchlist",
        "export_portfolio",
    }
    assert "get_portfolio_details" in names
    assert "Disabled tags configured" in caplog.text


@pytest.mark.asyncio
async def test_disabling_the_account_tag_hides_get_accounts(load_server):
    names = await tool_names(load_server(GHOSTFOLIO_DISABLED_TAGS="account"))

    assert "get_account_details" not in names
    assert "get_accounts" not in names


@pytest.mark.parametrize(
    ("strategy", "transform"),
    [("bm25", BM25SearchTransform), ("regex", RegexSearchTransform)],
)
@pytest.mark.asyncio
async def test_tool_search_replaces_the_tool_list(
    load_server, caplog, strategy, transform
):
    caplog.set_level(logging.INFO)
    server = load_server(
        TOOL_SEARCH_ENABLED="true",
        TOOL_SEARCH_STRATEGY=strategy,
        TOOL_SEARCH_MAX_RESULTS="7",
    )

    [search] = [t for t in server.mcp.transforms if isinstance(t, transform)]
    assert search._max_results == 7
    assert await tool_names(server) == {"search_tools", "call_tool"}
    assert f"strategy={strategy}, max_results=7" in caplog.text


def test_rate_limiting_adds_middleware(load_server):
    server = load_server(
        RATE_LIMIT_ENABLED="true",
        RATE_LIMIT_MAX_REQUESTS="5",
        RATE_LIMIT_WINDOW_MINUTES="2",
    )

    [limiter] = [
        m
        for m in server.mcp.middleware
        if isinstance(m, SlidingWindowRateLimitingMiddleware)
    ]
    assert limiter.max_requests == 5
    assert limiter.window_seconds == 120


def test_rate_limiting_is_off_by_default(load_server):
    server = load_server()

    assert not any(
        isinstance(m, SlidingWindowRateLimitingMiddleware)
        for m in server.mcp.middleware
    )


def test_unknown_log_level_falls_back_to_info(load_server, caplog):
    load_server(LOG_LEVEL="chatty")

    assert "Unknown LOG_LEVEL 'CHATTY'" in caplog.text


def test_version_comes_from_the_installed_package(load_server):
    assert load_server().__version__ == importlib.metadata.version("ghostfolio-mcp")


def test_version_falls_back_when_package_is_not_installed(load_server, monkeypatch):
    def missing(_name):
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(importlib.metadata, "version", missing)

    assert load_server().__version__ == "0.0.1"


def test_invalid_configuration_is_logged_and_raised(load_server, caplog):
    with pytest.raises(ValueError, match="TOOL_SEARCH_STRATEGY"):
        load_server(TOOL_SEARCH_ENABLED="true", TOOL_SEARCH_STRATEGY="regx")

    assert "Invalid configuration" in caplog.text


def test_bearer_token_enables_auth(load_server):
    assert load_server().mcp.auth is None
    assert isinstance(
        load_server(MCP_HTTP_BEARER_TOKEN="secret").mcp.auth, StaticTokenVerifier
    )


def test_main_runs_stdio_by_default(load_server, caplog):
    caplog.set_level(logging.INFO)
    server = load_server()

    server.main()

    server.mcp.run.assert_called_once_with()
    assert "Using STDIO transport" in caplog.text
    assert "WITHOUT authentication" not in caplog.text


@pytest.mark.parametrize("transport", ["http", "sse"])
def test_main_runs_http_transports_on_the_configured_address(
    load_server, caplog, transport
):
    caplog.set_level(logging.INFO)
    server = load_server(
        MCP_TRANSPORT=transport,
        MCP_HTTP_HOST="192.0.2.10",
        MCP_HTTP_PORT="9001",
        MCP_HTTP_BEARER_TOKEN="secret",
    )

    server.main()

    server.mcp.run.assert_called_once_with(
        transport=transport, host="192.0.2.10", port=9001
    )
    assert "on 192.0.2.10:9001" in caplog.text
    assert "Bearer token authentication enabled" in caplog.text
    assert "WITHOUT authentication" not in caplog.text


@pytest.mark.parametrize("transport", ["http", "sse"])
def test_main_warns_when_http_runs_without_a_token(load_server, caplog, transport):
    server = load_server(MCP_TRANSPORT=transport)

    server.main()

    server.mcp.run.assert_called_once()
    assert "WITHOUT authentication" in caplog.text
    assert "Bearer token authentication enabled" not in caplog.text


@pytest.mark.parametrize(
    ("transport", "label"), [("http", "Streamable"), ("sse", "SSE")]
)
def test_main_reports_oidc_instead_of_warning(
    load_server, monkeypatch, caplog, transport, label
):
    caplog.set_level(logging.INFO)
    server = load_server(MCP_TRANSPORT=transport)
    # OIDCProxy runs discovery against the upstream when constructed, so the
    # OIDC settings are swapped in after import; main() only reads the config.
    monkeypatch.setattr(
        server,
        "TRANSPORT_CONFIG",
        TransportConfig(
            transport_type=transport, http_bearer_token="secret", **OIDC_SETTINGS
        ),
    )

    server.main()

    server.mcp.run.assert_called_once_with(
        transport=transport, host="127.0.0.1", port=8000
    )
    assert f"OIDC authentication enabled for {label} transport" in caplog.text
    assert "Bearer token authentication enabled" not in caplog.text
    assert "WITHOUT authentication" not in caplog.text


def test_main_rejects_an_unknown_transport(load_server, caplog):
    server = load_server(MCP_TRANSPORT="websocket")

    with pytest.raises(SystemExit) as exc:
        server.main()

    assert exc.value.code == 1
    assert "Unknown MCP_TRANSPORT 'websocket'" in caplog.text
    server.mcp.run.assert_not_called()


@pytest.mark.parametrize("missing", ["GHOSTFOLIO_URL", "GHOSTFOLIO_TOKEN"])
def test_main_requires_url_and_token(load_server, caplog, missing):
    server = load_server(**{missing: ""})

    with pytest.raises(SystemExit) as exc:
        server.main()

    assert exc.value.code == 1
    assert "Missing required Ghostfolio configuration" in caplog.text
    server.mcp.run.assert_not_called()
