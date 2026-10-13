import logging
import os
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

import httpx2

from ghostfolio_mcp.models import GhostfolioConfig
from ghostfolio_mcp.models import TransportConfig
from ghostfolio_mcp.utils import HTTP_TRANSPORTS
from ghostfolio_mcp.utils import env_bool
from ghostfolio_mcp.utils import env_int
from ghostfolio_mcp.utils import env_str
from ghostfolio_mcp.utils import http_host_from_env
from ghostfolio_mcp.utils import http_port_from_env
from ghostfolio_mcp.utils import quote_path_segment
from ghostfolio_mcp.utils import transport_from_env

logger = logging.getLogger(__name__)

# Response bodies are attacker/server controlled and can be arbitrarily large
# (e.g. an HTML error page from a misconfigured reverse proxy); truncate what
# we fold into an exception message.
_MAX_ERROR_BODY_LENGTH = 2000


def _annotate_with_response_body(exc: httpx2.HTTPStatusError) -> httpx2.HTTPStatusError:
    """Fold the response body into an HTTPStatusError's message.

    httpx2's own message (e.g. "Client error '400 Bad Request' for url ...")
    omits the body, which is where Ghostfolio's NestJS validation errors put
    the actual reason. Re-raising a new instance with the same request/response
    keeps ``exc.response.status_code`` usable by callers that inspect it
    (see assets.py's upsert_asset_profile) while making the body visible
    wherever the exception is stringified.
    """
    body = exc.response.text.strip()
    if len(body) > _MAX_ERROR_BODY_LENGTH:
        body = body[:_MAX_ERROR_BODY_LENGTH] + "... (truncated)"
    message = str(exc)
    if body:
        message = f"{message} | response body: {body}"
    return httpx2.HTTPStatusError(message, request=exc.request, response=exc.response)


class GhostfolioClient:
    """Async client for Ghostfolio API using API token authentication"""

    _instance = None
    _initialized = False

    def __new__(cls, config: GhostfolioConfig | None = None):  # noqa: ARG004
        """Create a new instance of GhostfolioClient."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: GhostfolioConfig | None = None):
        """Initialize the GhostfolioClient."""
        if self._initialized:
            return
        if config is None:
            raise ValueError("Config must be provided for first initialization")
        self.config = config
        # Ensure trailing slash for base_url
        base = config.ghostfolio_url.rstrip("/")
        self.base_url = f"{base}/api"
        self.client: httpx2.AsyncClient | None = None
        self._jwt_token: str | None = None
        self._jwt_token_expiry: datetime | None = None
        self._initialized = True

    async def __aenter__(self):
        """Enter the async context manager."""
        if self.client is None:
            self.client = httpx2.AsyncClient(
                verify=self.config.verify_ssl,
                timeout=self.config.timeout,
                base_url=self.base_url,
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager."""
        # Keep client for reuse
        pass

    async def close(self):
        """Close the HTTP client session."""
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    async def _refresh_jwt_token(self) -> None:
        """Refresh JWT token if expired or not present."""
        if (
            self._jwt_token is not None
            and self._jwt_token_expiry
            and self._jwt_token_expiry > datetime.now(UTC)
        ):
            return

        if self.client is None:
            raise RuntimeError("Client not initialized")

        resp = await self.client.post(
            "/v1/auth/anonymous/", json={"accessToken": self.config.token}
        )
        try:
            resp.raise_for_status()
        except httpx2.HTTPStatusError as exc:
            raise _annotate_with_response_body(exc) from exc
        result = resp.json()
        self._jwt_token = result["authToken"]
        self._jwt_token_expiry = datetime.now(UTC) + timedelta(days=30)

    async def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        api_version: str = "v1",
        object_id: str | None = None,
    ) -> dict[str, Any]:
        """Perform a request to a Ghostfolio API path."""
        if self.client is None:
            raise RuntimeError(
                "Client not initialized - use 'async with GhostfolioClient(config)' or call __aenter__"
            )

        await self._refresh_jwt_token()

        # Build URL path. Callers assemble `path` themselves and must encode any
        # caller-supplied segment with utils.quote_path_segment; `object_id` is a
        # single segment, so it is encoded here.
        #
        # Ghostfolio's NestJS routes are inconsistent on the
        # trailing slash: most GET endpoints (asset, portfolio, account, etc.)
        # require the trailing slash, while several POST/PATCH/DELETE
        # endpoints — notably /market-data/MANUAL/<symbol>, /admin/profile-data
        # /MANUAL/<symbol>, and /order/<id> — return 404 *with* the trailing
        # slash. Match the slash to the method.
        url_path = f"/{api_version}/{path.lstrip('/')}"
        if object_id:
            url_path = f"{url_path.rstrip('/')}/{quote_path_segment(object_id)}"

        # Path-specific trailing slash logic because Ghostfolio's NestJS is inconsistent
        if method.upper() == "GET":
            # These paths specifically do NOT want a trailing slash
            no_slash_paths = ["/market-data/", "/portfolio/holding/", "/symbol/"]
            needs_slash = True
            for nsp in no_slash_paths:
                if f"/{api_version}{nsp}" in url_path or url_path.startswith(
                    f"/{api_version}{nsp}"
                ):
                    needs_slash = False
                    break

            if needs_slash and not url_path.endswith("/"):
                url_path += "/"
        else:
            url_path = url_path.rstrip("/")

        headers = {"Authorization": f"Bearer {self._jwt_token}"}
        resp = await self.client.request(
            method, url_path, params=params, json=data, headers=headers
        )
        try:
            resp.raise_for_status()
        except httpx2.HTTPStatusError as exc:
            raise _annotate_with_response_body(exc) from exc
        # Some Ghostfolio admin endpoints (e.g. PATCH
        # /admin/profile-data/MANUAL/<symbol>) return 200 with an empty body.
        # resp.json() raises JSONDecodeError on empty content; treat empty as
        # an empty dict.
        if not resp.content:
            return {}
        return resp.json()

    async def get(
        self, path: str, params: dict[str, Any] | None = None, api_version: str = "v1"
    ) -> dict[str, Any]:
        """Perform a GET request to a Ghostfolio API path."""
        return await self.request("GET", path, params=params, api_version=api_version)

    async def post(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        api_version: str = "v1",
        object_id: str | None = None,
    ) -> dict[str, Any]:
        """Perform a POST request to a Ghostfolio API path."""
        return await self.request(
            "POST", path, data=data, api_version=api_version, object_id=object_id
        )

    async def put(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        api_version: str = "v1",
        object_id: str | None = None,
    ) -> dict[str, Any]:
        """Perform a PUT request to a Ghostfolio API path."""
        return await self.request(
            "PUT", path, data=data, api_version=api_version, object_id=object_id
        )

    async def patch(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        api_version: str = "v1",
        object_id: str | None = None,
    ) -> dict[str, Any]:
        """Perform a PATCH request to a Ghostfolio API path."""
        return await self.request(
            "PATCH", path, data=data, api_version=api_version, object_id=object_id
        )

    async def delete(
        self, path: str, params: dict[str, Any] | None = None, api_version: str = "v1"
    ) -> dict[str, Any]:
        """Perform a DELETE request to a Ghostfolio API path."""
        return await self.request(
            "DELETE", path, params=params, api_version=api_version
        )


def _env_setting(name: str, field: str) -> int:
    """Read an integer setting, defaulting to GhostfolioConfig's own default."""
    return env_int(name, GhostfolioConfig.model_fields[field].default)


def get_ghostfolio_config_from_env() -> GhostfolioConfig:
    """Get Ghostfolio configuration from environment variables."""
    # Parse disabled tags from comma-separated string
    disabled_tags_str = os.getenv("GHOSTFOLIO_DISABLED_TAGS", "")
    disabled_tags = set()
    if disabled_tags_str.strip():
        # Split by comma and strip whitespace from each tag
        disabled_tags = {
            tag.strip() for tag in disabled_tags_str.split(",") if tag.strip()
        }

    # Unknown values used to fall back to bm25 silently, hiding a typo such as
    # "regx"; refuse them - but only when tool search is on, so a leftover
    # value cannot stop a server that never uses it.
    tool_search_enabled = env_bool("TOOL_SEARCH_ENABLED", default=False)
    tool_search_strategy = (env_str("TOOL_SEARCH_STRATEGY") or "bm25").lower()
    if tool_search_enabled and tool_search_strategy not in ("bm25", "regex"):
        raise ValueError(
            "TOOL_SEARCH_STRATEGY must be 'bm25' or 'regex', "
            f"got {os.getenv('TOOL_SEARCH_STRATEGY')!r}"
        )
    rate_limit_enabled = env_bool("RATE_LIMIT_ENABLED", default=False)

    # Numeric settings of a disabled feature are not read at all: a leftover
    # value must not stop a server that never uses it, and GhostfolioConfig's
    # own defaults then apply. Read ones fall back to those same defaults.
    numbers: dict[str, int] = {}
    if rate_limit_enabled:
        numbers["rate_limit_max_requests"] = _env_setting(
            "RATE_LIMIT_MAX_REQUESTS", "rate_limit_max_requests"
        )
        numbers["rate_limit_window_minutes"] = _env_setting(
            "RATE_LIMIT_WINDOW_MINUTES", "rate_limit_window_minutes"
        )
    if tool_search_enabled:
        numbers["tool_search_max_results"] = _env_setting(
            "TOOL_SEARCH_MAX_RESULTS", "tool_search_max_results"
        )

    return GhostfolioConfig(
        ghostfolio_url=env_str("GHOSTFOLIO_URL") or "",
        token=env_str("GHOSTFOLIO_TOKEN") or "",
        verify_ssl=env_bool("GHOSTFOLIO_VERIFY_SSL", default=True),
        timeout=_env_setting("GHOSTFOLIO_TIMEOUT", "timeout"),
        read_only_mode=env_bool("READ_ONLY_MODE", default=False),
        disabled_tags=disabled_tags,
        rate_limit_enabled=rate_limit_enabled,
        tool_search_enabled=tool_search_enabled,
        tool_search_strategy="regex" if tool_search_strategy == "regex" else "bm25",
        **numbers,
    )


def get_transport_config_from_env() -> TransportConfig:
    """Get transport configuration from environment variables."""

    def _csv(name: str) -> list[str] | None:
        """Read a comma-separated env var, treating a blank value as unset."""
        raw = env_str(name)
        if raw is None:
            return None
        return [item.strip() for item in raw.split(",") if item.strip()] or None

    transport_type = transport_from_env()
    # The port is only parsed when an HTTP transport will bind it: a leftover
    # non-numeric MCP_HTTP_PORT must not stop stdio or `fastmcp run`.
    http_port = http_port_from_env() if transport_type in HTTP_TRANSPORTS else 8000

    return TransportConfig(
        transport_type=transport_type,
        http_host=http_host_from_env(),
        http_port=http_port,
        http_bearer_token=env_str("MCP_HTTP_BEARER_TOKEN"),
        oidc_config_url=env_str("OIDC_CONFIG_URL"),
        oidc_client_id=env_str("OIDC_CLIENT_ID"),
        oidc_client_secret=env_str("OIDC_CLIENT_SECRET"),
        oidc_base_url=env_str("OIDC_BASE_URL"),
        oidc_redirect_path=env_str("OIDC_REDIRECT_PATH") or "/auth/callback",
        oidc_required_scopes=_csv("OIDC_REQUIRED_SCOPES"),
        oidc_allowed_redirect_uris=_csv("OIDC_ALLOWED_REDIRECT_URIS"),
        oidc_verify_id_token=env_bool("OIDC_VERIFY_ID_TOKEN", default=False),
        oidc_forward_resource=env_bool("OIDC_FORWARD_RESOURCE", default=False),
    )


_ghostfolio_client_singleton: GhostfolioClient | None = None


def get_ghostfolio_client(config: GhostfolioConfig | None = None) -> GhostfolioClient:
    """Get the singleton Ghostfolio client instance."""
    global _ghostfolio_client_singleton
    if _ghostfolio_client_singleton is None:
        if config is None:
            raise ValueError(
                "Ghostfolio config must be provided for first initialization"
            )
        _ghostfolio_client_singleton = GhostfolioClient(config)
    return _ghostfolio_client_singleton
