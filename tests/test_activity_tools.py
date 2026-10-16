"""Tests for the activity write tools, including tags support.

Covers create_activity's optional `tags` passthrough and the new
update_activity tool, which mirrors update_account's backfill-from-GET
pattern because Ghostfolio's UpdateOrderDto also replaces the whole activity
record on every PUT.
"""

import json

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


async def call(mcp: FastMCP, name: str, arguments: dict):
    tool = await mcp.get_tool(name)
    assert tool is not None, f"tool {name!r} is not registered"
    return await tool.run(arguments)


@pytest.mark.asyncio
async def test_create_activity_omits_tags_when_not_provided(recorder):
    mcp, requests, _responses = recorder

    await call(
        mcp,
        "create_activity",
        {
            "type": "BUY",
            "symbol": "VFIAX",
            "date": "2026-09-28T00:00:00.000Z",
            "quantity": 0.249,
            "unit_price": 708.94,
            "currency": "USD",
            "data_source": "YAHOO",
            "account_id": "acc-1",
        },
    )

    body = json.loads(requests[0].content)
    assert "tags" not in body


@pytest.mark.asyncio
async def test_create_activity_passes_through_tags(recorder):
    mcp, requests, _responses = recorder

    await call(
        mcp,
        "create_activity",
        {
            "type": "BUY",
            "symbol": "VFIAX",
            "date": "2026-09-28T00:00:00.000Z",
            "quantity": 0.249,
            "unit_price": 708.94,
            "currency": "USD",
            "data_source": "YAHOO",
            "account_id": "acc-1",
            "tags": ["a1bbe3e0-628b-4cdf-bf7c-78e0fe3a0b17"],
        },
    )

    body = json.loads(requests[0].content)
    assert body["tags"] == ["a1bbe3e0-628b-4cdf-bf7c-78e0fe3a0b17"]


@pytest.mark.asyncio
async def test_update_activity_backfills_required_fields_from_current_activity(
    recorder,
):
    mcp, requests, responses = recorder
    responses.append(
        httpx2.Response(
            200,
            json={
                "id": "act-1",
                "type": "BUY",
                "date": "2026-09-28T00:00:00.000Z",
                "quantity": 0.249,
                "unitPrice": 708.94,
                "currency": "USD",
                "fee": 0.0,
                "comment": None,
                "accountId": "acc-1",
                "SymbolProfile": {"symbol": "VFIAX", "dataSource": "YAHOO"},
                "tags": [
                    {"id": "a1bbe3e0-628b-4cdf-bf7c-78e0fe3a0b17", "name": "Retirement"}
                ],
            },
        )
    )

    await call(mcp, "update_activity", {"activity_id": "act-1", "fee": 1.5})

    assert len(requests) == 2
    get_request, put_request = requests
    assert get_request.method == "GET"
    assert get_request.url.path == "/api/v1/activities/act-1/"
    assert put_request.method == "PUT"
    body = json.loads(put_request.content)
    assert body == {
        "id": "act-1",
        "type": "BUY",
        "symbol": "VFIAX",
        "date": "2026-09-28T00:00:00.000Z",
        "quantity": 0.249,
        "unitPrice": 708.94,
        "currency": "USD",
        "dataSource": "YAHOO",
        "fee": 1.5,
        "tags": ["a1bbe3e0-628b-4cdf-bf7c-78e0fe3a0b17"],
        "accountId": "acc-1",
    }


@pytest.mark.asyncio
async def test_update_activity_overrides_tags_take_precedence_over_current_tags(
    recorder,
):
    mcp, requests, responses = recorder
    responses.append(
        httpx2.Response(
            200,
            json={
                "id": "act-1",
                "type": "BUY",
                "date": "2026-09-28T00:00:00.000Z",
                "quantity": 0.249,
                "unitPrice": 708.94,
                "currency": "USD",
                "fee": 0.0,
                "accountId": "acc-1",
                "SymbolProfile": {"symbol": "VFIAX", "dataSource": "YAHOO"},
                "tags": [{"id": "old-tag", "name": "Old"}],
            },
        )
    )

    await call(
        mcp,
        "update_activity",
        {"activity_id": "act-1", "tags": ["a1bbe3e0-628b-4cdf-bf7c-78e0fe3a0b17"]},
    )

    body = json.loads(requests[1].content)
    assert body["tags"] == ["a1bbe3e0-628b-4cdf-bf7c-78e0fe3a0b17"]


@pytest.mark.asyncio
async def test_update_activity_can_clear_tags_with_empty_list(recorder):
    mcp, requests, responses = recorder
    responses.append(
        httpx2.Response(
            200,
            json={
                "id": "act-1",
                "type": "BUY",
                "date": "2026-09-28T00:00:00.000Z",
                "quantity": 0.249,
                "unitPrice": 708.94,
                "currency": "USD",
                "fee": 0.0,
                "accountId": "acc-1",
                "SymbolProfile": {"symbol": "VFIAX", "dataSource": "YAHOO"},
                "tags": [{"id": "old-tag", "name": "Old"}],
            },
        )
    )

    await call(mcp, "update_activity", {"activity_id": "act-1", "tags": []})

    body = json.loads(requests[1].content)
    assert body["tags"] == []
