"""Tests for outbound User-Agent configuration and header injection."""

import httpx2
import pytest

from ghostfolio_mcp import ghostfolio_client as client_module
from ghostfolio_mcp.ghostfolio_client import DEFAULT_USER_AGENT
from ghostfolio_mcp.ghostfolio_client import GhostfolioClient
from ghostfolio_mcp.ghostfolio_client import get_ghostfolio_config_from_env
from ghostfolio_mcp.models import GhostfolioConfig


def test_env_user_agent_defaults_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GHOSTFOLIO_URL", "https://ghostfolio.test")
    monkeypatch.setenv("GHOSTFOLIO_TOKEN", "api-token")
    monkeypatch.delenv("GHOSTFOLIO_USER_AGENT", raising=False)

    assert get_ghostfolio_config_from_env().user_agent is None

    monkeypatch.setenv("GHOSTFOLIO_USER_AGENT", "  custom-ghostfolio/1.0  ")
    assert get_ghostfolio_config_from_env().user_agent == "custom-ghostfolio/1.0"

    monkeypatch.setenv("GHOSTFOLIO_USER_AGENT", "   ")
    assert get_ghostfolio_config_from_env().user_agent is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        (None, DEFAULT_USER_AGENT),
        ("custom-ghostfolio/1.0", "custom-ghostfolio/1.0"),
    ],
)
async def test_outbound_requests_send_user_agent(
    monkeypatch: pytest.MonkeyPatch, configured: str | None, expected: str
) -> None:
    seen: list[str | None] = []
    real_async_client = httpx2.AsyncClient

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request.headers.get("User-Agent"))
        if request.url.path.rstrip("/").endswith("/auth/anonymous"):
            return httpx2.Response(200, json={"authToken": "jwt-token"})
        return httpx2.Response(200, json={"accounts": []})

    def patched_async_client(*args, **kwargs):
        kwargs["transport"] = httpx2.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx2, "AsyncClient", patched_async_client)

    GhostfolioClient._instance = None
    client_module._ghostfolio_client_singleton = None
    try:
        client = GhostfolioClient(
            GhostfolioConfig(
                ghostfolio_url="https://ghostfolio.test",
                token="api-token",
                verify_ssl=False,
                user_agent=configured,
            )
        )
        async with client:
            await client.get("/v1/account")
        await client.close()
    finally:
        GhostfolioClient._instance = None
        client_module._ghostfolio_client_singleton = None

    assert seen
    assert all(ua == expected for ua in seen)
