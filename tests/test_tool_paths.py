"""End-to-end checks that tool arguments cannot rewrite the request path.

These drive the registered tools with a mocked httpx2 transport and assert on
the raw path that reaches the wire, which is the only place the bug was
observable: a symbol containing '#' or '/' used to change which resource the
request addressed, so writes and deletes silently hit a different symbol and
returned success for it.
"""

import httpx2
import pytest

from tests.helpers import call


def raw_paths(requests: list[httpx2.Request]) -> list[str]:
    """The undecoded path of each request, as it went over the wire."""
    return [request.url.raw_path.decode() for request in requests]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "arguments", "expected"),
    [
        # Reads.
        (
            "get_asset_profile",
            {"data_source": "MANUAL", "symbol": "A#B"},
            "/api/v1/asset/MANUAL/A%23B/",
        ),
        (
            "get_symbol_data",
            {"data_source": "MANUAL", "symbol": "BTC/USD"},
            "/api/v1/symbol/MANUAL/BTC%2FUSD",
        ),
        (
            "get_historical_data",
            {"data_source": "MANUAL", "symbol": "A#B", "date": "2026-04-30"},
            "/api/v1/symbol/MANUAL/A%23B/2026-04-30",
        ),
        (
            "get_market_data_for_asset",
            {"data_source": "MANUAL", "symbol": "A#B"},
            "/api/v1/market-data/MANUAL/A%23B",
        ),
        (
            "get_position",
            {"data_source": "MANUAL", "symbol": "A#B"},
            "/api/v1/portfolio/holding/MANUAL/A%23B",
        ),
        (
            "get_exchange_rate",
            {"symbol": "US/D", "date": "2026-04-30"},
            "/api/v1/exchange-rate/US%2FD/2026-04-30/",
        ),
        (
            "get_dividends_for_import",
            {"data_source": "MANUAL", "symbol": "A#B"},
            "/api/v1/import/dividends/MANUAL/A%23B/",
        ),
        (
            "get_account_balances",
            {"account_id": "a#b"},
            "/api/v1/account/a%23b/balances/",
        ),
        (
            "get_account_details",
            {"account_id": "a#b"},
            "/api/v1/account/a%23b/",
        ),
        # Writes and deletes - the cases where a rewritten path meant acting on
        # the wrong resource rather than just reading the wrong one.
        (
            "add_market_data_points",
            {
                "data_source": "MANUAL",
                "symbol": "A#B",
                "market_data": [
                    {"date": "2026-04-30T00:00:00.000Z", "marketPrice": 1.0}
                ],
            },
            "/api/v1/market-data/MANUAL/A%23B",
        ),
        (
            "delete_asset_profile",
            {"data_source": "MANUAL", "symbol": "A#B"},
            "/api/v1/admin/profile-data/MANUAL/A%23B",
        ),
        (
            "remove_from_watchlist",
            {"data_source": "MANUAL", "symbol": "A#B"},
            "/api/v1/watchlist/MANUAL/A%23B",
        ),
        (
            "delete_activity",
            {"activity_id": "a#b"},
            "/api/v1/activities/a%23b",
        ),
        (
            "delete_account",
            {"account_id": "a#b"},
            "/api/v1/account/a%23b",
        ),
        (
            "delete_account_balance",
            {"balance_id": "a#b"},
            "/api/v1/account-balance/a%23b",
        ),
    ],
)
async def test_path_segments_are_encoded(recorder, name, arguments, expected):
    mcp, requests, _responses = recorder
    await call(mcp, name, arguments)
    assert raw_paths(requests) == [expected]


@pytest.mark.asyncio
async def test_upsert_asset_profile_encodes_both_requests(recorder):
    mcp, requests, _responses = recorder
    await call(
        mcp,
        "upsert_asset_profile",
        {
            "data_source": "MANUAL",
            "symbol": "A#B",
            "name": "Some asset",
            "currency": "USD",
            "asset_class": "EQUITY",
        },
    )
    # POST then PATCH, both against the encoded symbol.
    assert raw_paths(requests) == [
        "/api/v1/admin/profile-data/MANUAL/A%23B",
        "/api/v1/admin/profile-data/MANUAL/A%23B",
    ]


@pytest.mark.asyncio
async def test_update_account_encodes_both_requests(recorder):
    mcp, requests, _responses = recorder
    await call(mcp, "update_account", {"account_id": "a#b", "name": "renamed"})
    # GET to backfill required fields, then PUT, both against the encoded id.
    assert raw_paths(requests) == [
        "/api/v1/account/a%23b/",
        "/api/v1/account/a%23b",
    ]


@pytest.mark.asyncio
async def test_update_activity_encodes_both_requests(recorder):
    mcp, requests, _responses = recorder
    await call(
        mcp,
        "update_activity",
        {
            "activity_id": "a#b",
            "type": "BUY",
            "symbol": "AAPL",
            "date": "2026-04-30T00:00:00.000Z",
            "quantity": 1.0,
            "unit_price": 1.0,
            "currency": "USD",
            "data_source": "YAHOO",
            "fee": 0.0,
            "comment": "",
        },
    )
    # GET to backfill required fields, then PUT, both against the encoded id.
    assert raw_paths(requests) == [
        "/api/v1/activities/a%23b/",
        "/api/v1/activities/a%23b",
    ]


@pytest.mark.asyncio
async def test_dot_segment_cannot_walk_up_the_path(recorder):
    mcp, requests, _responses = recorder
    await call(mcp, "delete_asset_profile", {"data_source": "MANUAL", "symbol": ".."})
    # Unescaped this would normalise to /api/v1/admin/profile-data, deleting
    # against the collection instead of the symbol.
    assert raw_paths(requests) == ["/api/v1/admin/profile-data/MANUAL/%2E%2E"]


@pytest.mark.asyncio
async def test_empty_id_does_not_reach_the_collection_endpoint(recorder):
    mcp, requests, _responses = recorder
    # DELETE /api/v1/activities (no id) deletes every activity, so an empty id
    # has to fail before the request is built.
    with pytest.raises(Exception, match="must not be empty"):
        await call(mcp, "delete_activity", {"activity_id": ""})
    assert raw_paths(requests) == []
