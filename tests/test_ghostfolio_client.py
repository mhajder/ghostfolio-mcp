"""Tests for GhostfolioClient's lifecycle, authentication and request building."""

import json

import httpx2
import pytest

from ghostfolio_mcp import ghostfolio_client as client_module
from ghostfolio_mcp.ghostfolio_client import GhostfolioClient
from ghostfolio_mcp.ghostfolio_client import get_ghostfolio_client
from ghostfolio_mcp.models import GhostfolioConfig
from tests.conftest import AUTH_PATH
from tests.conftest import BASE_URL


@pytest.fixture(autouse=True)
def fresh_singleton():
    """Each test starts without a client, as a freshly started server does."""
    GhostfolioClient._instance = None
    client_module._ghostfolio_client_singleton = None
    yield
    GhostfolioClient._instance = None
    client_module._ghostfolio_client_singleton = None


@pytest.fixture
def config() -> GhostfolioConfig:
    return GhostfolioConfig(
        ghostfolio_url=f"{BASE_URL}/", token="api-token", verify_ssl=False, timeout=12
    )


def mocked(config: GhostfolioConfig, handler) -> GhostfolioClient:
    client = GhostfolioClient(config)
    client.client = httpx2.AsyncClient(
        base_url=client.base_url, transport=httpx2.MockTransport(handler)
    )
    return client


def test_client_is_a_singleton_that_keeps_its_first_config(config):
    first = GhostfolioClient(config)
    other = GhostfolioConfig(ghostfolio_url="https://other.test", token="other")

    second = GhostfolioClient(other)

    assert second is first
    assert second.config is config
    assert second.base_url == f"{BASE_URL}/api"


def test_first_client_needs_a_config():
    with pytest.raises(ValueError, match="Config must be provided"):
        GhostfolioClient()


def test_first_singleton_lookup_needs_a_config():
    with pytest.raises(ValueError, match="Ghostfolio config must be provided"):
        get_ghostfolio_client()


def test_singleton_lookup_returns_the_existing_client(config):
    client = get_ghostfolio_client(config)

    assert get_ghostfolio_client() is client


@pytest.mark.asyncio
async def test_entering_builds_an_http_client_from_the_config(config, monkeypatch):
    created: list[dict] = []
    real_async_client = httpx2.AsyncClient

    def spy(**kwargs):
        created.append(kwargs)
        return real_async_client(**kwargs)

    monkeypatch.setattr(httpx2, "AsyncClient", spy)
    client = GhostfolioClient(config)

    async with client as entered:
        assert entered is client
        http_client = client.client
    # Kept open after the block so the next tool call reuses it.
    async with client:
        assert client.client is http_client

    assert created == [{"verify": False, "timeout": 12, "base_url": f"{BASE_URL}/api"}]
    await client.close()


@pytest.mark.asyncio
async def test_close_releases_the_http_client_and_is_idempotent(config):
    client = GhostfolioClient(config)
    async with client:
        http_client = client.client
    assert http_client is not None

    await client.close()
    assert client.client is None
    assert http_client.is_closed

    await client.close()
    assert client.client is None


@pytest.mark.asyncio
async def test_request_without_an_http_client_fails_clearly(config):
    client = GhostfolioClient(config)

    with pytest.raises(RuntimeError, match="Client not initialized"):
        await client.get("user")


@pytest.mark.asyncio
async def test_token_refresh_without_an_http_client_fails_clearly(config):
    client = GhostfolioClient(config)

    with pytest.raises(RuntimeError, match="Client not initialized"):
        await client._refresh_jwt_token()


@pytest.mark.asyncio
async def test_jwt_is_fetched_once_and_sent_as_bearer(config):
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        if request.url.path == AUTH_PATH:
            return httpx2.Response(200, json={"authToken": "jwt"})
        return httpx2.Response(200, json={"ok": True})

    client = mocked(config, handler)

    assert await client.get("user") == {"ok": True}
    assert await client.get("user") == {"ok": True}

    auth, first, second = seen
    assert auth.method == "POST"
    assert auth.url.path == AUTH_PATH
    assert json.loads(auth.content) == {"accessToken": "api-token"}
    assert first.headers["Authorization"] == "Bearer jwt"
    assert second.headers["Authorization"] == "Bearer jwt"


@pytest.mark.asyncio
async def test_rejected_token_surfaces_the_auth_error_body(config):
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == AUTH_PATH
        return httpx2.Response(403, json={"message": "Forbidden token"})

    client = mocked(config, handler)

    with pytest.raises(httpx2.HTTPStatusError, match="Forbidden token") as exc_info:
        await client.get("user")
    assert exc_info.value.response.status_code == 403


@pytest.mark.asyncio
async def test_empty_success_body_is_an_empty_dict(config):
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == AUTH_PATH:
            return httpx2.Response(200, json={"authToken": "jwt"})
        return httpx2.Response(200, content=b"")

    client = mocked(config, handler)

    assert await client.patch("admin/profile-data/MANUAL/X", data={}) == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["post", "put", "patch"])
async def test_object_id_is_appended_as_one_encoded_segment(config, method):
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == AUTH_PATH:
            return httpx2.Response(200, json={"authToken": "jwt"})
        seen.append(request)
        return httpx2.Response(200, json={})

    client = mocked(config, handler)

    await getattr(client, method)("account/", data={"a": 1}, object_id="a/b")

    [request] = seen
    assert request.method == method.upper()
    assert request.url.raw_path.decode() == "/api/v1/account/a%2Fb"
    assert json.loads(request.content) == {"a": 1}
