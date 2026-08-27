"""Tests for the account and account-balance write tools.

Covers the fix for update_account's 400s (Ghostfolio's UpdateAccountDto
requires the full object - id, name, currency, platformId - on every PUT, so
fields the caller didn't override are backfilled from a GET), the new
account-balance create/delete tools, and that a failed write surfaces the
API's validation message instead of a bare status code.
"""

import json
from datetime import UTC
from datetime import datetime

import httpx
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

    requests: list[httpx.Request] = []
    responses: list[httpx.Response] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == AUTH_PATH:
            return httpx.Response(200, json={"authToken": "jwt"})
        requests.append(request)
        return responses.pop(0) if responses else httpx.Response(200, json={})

    # The client is a singleton twice over - a class attribute and a module
    # global - so reset both to give each test its own transport.
    GhostfolioClient._instance = None
    client_module._ghostfolio_client_singleton = None
    client = client_module.get_ghostfolio_client(config)
    client.client = httpx.AsyncClient(
        base_url=client.base_url, transport=httpx.MockTransport(handler)
    )

    yield mcp, requests, responses

    GhostfolioClient._instance = None
    client_module._ghostfolio_client_singleton = None


async def call(mcp: FastMCP, name: str, arguments: dict):
    tool = await mcp.get_tool(name)
    assert tool is not None, f"tool {name!r} is not registered"
    return await tool.run(arguments)


@pytest.mark.asyncio
async def test_update_account_backfills_required_fields_from_current_account(
    recorder,
):
    mcp, requests, responses = recorder
    responses.append(
        httpx.Response(
            200,
            json={
                "id": "acc-1",
                "name": "Interactive Brokers",
                "currency": "EUR",
                "platformId": "platform-1",
            },
        )
    )

    await call(mcp, "update_account", {"account_id": "acc-1", "balance": 1099.04})

    assert len(requests) == 2
    get_request, put_request = requests
    assert get_request.method == "GET"
    assert put_request.method == "PUT"
    body = json.loads(put_request.content)
    assert body == {
        "id": "acc-1",
        "name": "Interactive Brokers",
        "currency": "EUR",
        "platformId": "platform-1",
        "balance": 1099.04,
    }


@pytest.mark.asyncio
async def test_update_account_overrides_take_precedence_over_current_values(recorder):
    mcp, requests, responses = recorder
    responses.append(
        httpx.Response(
            200,
            json={
                "id": "acc-1",
                "name": "Old name",
                "currency": "USD",
                "platformId": "old-platform",
            },
        )
    )

    await call(
        mcp,
        "update_account",
        {"account_id": "acc-1", "name": "New name", "platform_id": "new-platform"},
    )

    body = json.loads(requests[1].content)
    assert body["name"] == "New name"
    assert body["platformId"] == "new-platform"
    assert body["currency"] == "USD"  # backfilled from the GET, left unchanged
    assert "balance" not in body


@pytest.mark.asyncio
async def test_create_account_balance_defaults_date_to_today(recorder):
    mcp, requests, _responses = recorder

    await call(mcp, "create_account_balance", {"account_id": "acc-1", "balance": 500.0})

    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == "/api/v1/account-balance"
    body = json.loads(request.content)
    assert body == {
        "accountId": "acc-1",
        "balance": 500.0,
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
    }


@pytest.mark.asyncio
async def test_create_account_balance_uses_explicit_date(recorder):
    mcp, requests, _responses = recorder

    await call(
        mcp,
        "create_account_balance",
        {"account_id": "acc-1", "balance": 500.0, "date": "2026-05-01"},
    )

    body = json.loads(requests[0].content)
    assert body["date"] == "2026-05-01"


@pytest.mark.asyncio
async def test_delete_account_balance_deletes_by_balance_id(recorder):
    mcp, requests, _responses = recorder

    await call(mcp, "delete_account_balance", {"balance_id": "bal-1"})

    assert len(requests) == 1
    assert requests[0].method == "DELETE"
    assert requests[0].url.path == "/api/v1/account-balance/bal-1"


@pytest.mark.asyncio
async def test_failed_write_surfaces_api_error_body(recorder):
    mcp, _requests, responses = recorder
    responses.append(
        httpx.Response(
            400,
            json={
                "message": ["currency must be a valid currency code"],
                "error": "Bad Request",
                "statusCode": 400,
            },
        )
    )

    with pytest.raises(
        httpx.HTTPStatusError, match="currency must be a valid currency code"
    ):
        await call(
            mcp, "create_account_balance", {"account_id": "acc-1", "balance": 100.0}
        )


@pytest.mark.asyncio
async def test_failed_write_error_body_is_truncated_when_large(recorder):
    mcp, _requests, responses = recorder
    responses.append(httpx.Response(400, text="x" * 5000))

    with pytest.raises(httpx.HTTPStatusError, match=r"\(truncated\)") as exc_info:
        await call(
            mcp, "create_account_balance", {"account_id": "acc-1", "balance": 100.0}
        )

    assert len(str(exc_info.value)) < 3000
