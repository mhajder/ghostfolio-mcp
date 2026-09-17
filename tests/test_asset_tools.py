"""Tests for the asset profile write tool.

Covers the optional `countries` and `sectors` overrides on
upsert_asset_profile: omitting them leaves the stored allocation
untouched, passing [] clears it explicitly.
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
    """A FastMCP server whose Ghostfolio client records every non-auth request."""
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


BASE_ARGS = {
    "data_source": "YAHOO",
    "symbol": "VWCE.DE",
    "name": "Vanguard FTSE All-World",
    "currency": "EUR",
    "asset_class": "EQUITY",
}


def patch_body(requests: list[httpx2.Request]) -> dict:
    patch_requests = [r for r in requests if r.method == "PATCH"]
    assert len(patch_requests) == 1
    return json.loads(patch_requests[0].content)


@pytest.mark.asyncio
async def test_upsert_asset_profile_omits_allocations_when_not_given(recorder):
    mcp, requests, _responses = recorder

    await call(mcp, "upsert_asset_profile", BASE_ARGS)

    body = patch_body(requests)
    assert body == {
        "name": "Vanguard FTSE All-World",
        "currency": "EUR",
        "assetClass": "EQUITY",
    }


@pytest.mark.asyncio
async def test_upsert_asset_profile_forwards_countries_and_sectors(recorder):
    mcp, requests, _responses = recorder
    countries = [{"code": "US", "weight": 0.6907}, {"code": "JP", "weight": 0.0567}]
    sectors = [{"name": "Technology", "weight": 0.2431}]

    await call(
        mcp,
        "upsert_asset_profile",
        {
            **BASE_ARGS,
            "asset_sub_class": "ETF",
            "countries": countries,
            "sectors": sectors,
        },
    )

    body = patch_body(requests)
    assert body == {
        "name": "Vanguard FTSE All-World",
        "currency": "EUR",
        "assetClass": "EQUITY",
        "assetSubClass": "ETF",
        "countries": countries,
        "sectors": sectors,
    }


@pytest.mark.asyncio
async def test_upsert_asset_profile_sends_empty_list_to_clear_allocation(recorder):
    mcp, requests, _responses = recorder

    await call(mcp, "upsert_asset_profile", {**BASE_ARGS, "countries": []})

    body = patch_body(requests)
    assert body["countries"] == []
    assert "sectors" not in body


@pytest.mark.asyncio
async def test_upsert_asset_profile_tolerates_500_from_create(recorder):
    mcp, requests, responses = recorder
    responses.append(httpx2.Response(500, json={"statusCode": 500}))

    await call(mcp, "upsert_asset_profile", {**BASE_ARGS, "countries": []})

    assert [r.method for r in requests] == ["POST", "PATCH"]
    assert requests[1].url.path == "/api/v1/admin/profile-data/YAHOO/VWCE.DE"


@pytest.mark.asyncio
async def test_upsert_asset_profile_patches_existing_profile(recorder):
    """Overriding an auto-fetched profile: the create step 400s, PATCH still runs."""
    mcp, requests, responses = recorder
    responses.append(
        httpx2.Response(
            400,
            json={
                "message": "Asset profile of VWCE.DE (YAHOO) already exists",
                "error": "Bad Request",
                "statusCode": 400,
            },
        )
    )

    countries = [{"code": "US", "weight": 0.6907}]
    await call(mcp, "upsert_asset_profile", {**BASE_ARGS, "countries": countries})

    assert [r.method for r in requests] == ["POST", "PATCH"]
    assert patch_body(requests)["countries"] == countries


@pytest.mark.asyncio
async def test_upsert_asset_profile_surfaces_unknown_symbol_from_create(recorder):
    mcp, requests, responses = recorder
    responses.append(
        httpx2.Response(
            400,
            json={
                "message": "Asset profile not found for NOPE.DE (YAHOO)",
                "error": "Bad Request",
                "statusCode": 400,
            },
        )
    )

    with pytest.raises(httpx2.HTTPStatusError, match="Asset profile not found"):
        await call(mcp, "upsert_asset_profile", {**BASE_ARGS, "symbol": "NOPE.DE"})

    assert [r.method for r in requests] == ["POST"]
