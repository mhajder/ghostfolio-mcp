import httpx2
import pytest
from fastmcp import FastMCP

from ghostfolio_mcp import ghostfolio_client as client_module
from ghostfolio_mcp.ghostfolio_client import GhostfolioClient
from ghostfolio_mcp.models import GhostfolioConfig
from ghostfolio_mcp.tools import register_tools

BASE_URL = "https://ghostfolio.test:3333"
AUTH_PATH = "/api/v1/auth/anonymous/"


@pytest.fixture
def recorder():
    """A FastMCP server whose Ghostfolio client records every non-auth request.

    `responses` is consumed in call order for whatever the test needs the
    upstream API to return; any request beyond that gets a bare 200 `{}`.
    """
    config = GhostfolioConfig(ghostfolio_url=BASE_URL, token="api-token")

    mcp = FastMCP(name="test")
    register_tools(mcp, config)

    requests: list[httpx2.Request] = []
    responses: list[httpx2.Response] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == AUTH_PATH:
            return httpx2.Response(200, json={"authToken": "jwt"})
        requests.append(request)
        return responses.pop(0) if responses else httpx2.Response(200, json={})

    # The client is a singleton twice over - a class attribute and a module
    # global - so reset both to give each test its own transport.
    GhostfolioClient._instance = None
    client_module._ghostfolio_client_singleton = None
    client = client_module.get_ghostfolio_client(config)
    client.client = httpx2.AsyncClient(
        base_url=client.base_url, transport=httpx2.MockTransport(handler)
    )

    yield mcp, requests, responses

    GhostfolioClient._instance = None
    client_module._ghostfolio_client_singleton = None
