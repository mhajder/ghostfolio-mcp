"""The request each pass-through tool sends to Ghostfolio, and what it returns.

These tools add no logic beyond building the request, so the method, path,
query string and body that reach the wire are their whole behaviour.
"""

import json

import httpx2
import pytest

from tests.helpers import call


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "arguments", "path", "params"),
    [
        ("get_portfolio_details", {}, "/api/v1/portfolio/details/", {}),
        (
            "get_dividends",
            {},
            "/api/v1/portfolio/dividends/",
            {"range": "max", "groupBy": "month"},
        ),
        (
            "get_dividends",
            {"group_by": "year", "date_range": "5y"},
            "/api/v1/portfolio/dividends/",
            {"range": "5y", "groupBy": "year"},
        ),
        ("get_portfolio_holdings", {}, "/api/v1/portfolio/holdings/", {"range": "max"}),
        (
            "get_portfolio_holdings",
            {"date_range": "1y"},
            "/api/v1/portfolio/holdings/",
            {"range": "1y"},
        ),
        (
            "get_investments",
            {"group_by": "quarter", "date_range": "2y"},
            "/api/v1/portfolio/investments/",
            {"range": "2y", "groupBy": "quarter"},
        ),
        # Performance lives under the v2 API.
        (
            "get_portfolio_performance",
            {"date_range": "1m"},
            "/api/v2/portfolio/performance/",
            {"range": "1m"},
        ),
        ("get_benchmarks", {}, "/api/v1/benchmarks/", {}),
        (
            "get_benchmark_performance",
            {"data_source": "YAHOO", "symbol": "URTH", "start_date": "2024-01-01"},
            "/api/v1/benchmarks/YAHOO/URTH/2024-01-01/",
            {"range": "max", "withExcludedAccounts": "false"},
        ),
        (
            "get_benchmark_performance",
            {
                "data_source": "YAHOO",
                "symbol": "URTH",
                "start_date": "2024-01-01",
                "date_range": "1y",
                "accounts": "acc-1,acc-2",
                "asset_classes": "EQUITY",
                "filter_data_source": "COINGECKO",
                "filter_symbol": "bitcoin",
                "tags": "core",
                "with_excluded_accounts": True,
            },
            "/api/v1/benchmarks/YAHOO/URTH/2024-01-01/",
            {
                "range": "1y",
                "withExcludedAccounts": "true",
                "accounts": "acc-1,acc-2",
                "assetClasses": "EQUITY",
                "dataSource": "COINGECKO",
                "symbol": "bitcoin",
                "tags": "core",
            },
        ),
        ("export_portfolio", {}, "/api/v1/export/", {}),
        (
            "export_portfolio",
            {
                "accounts": "acc-1",
                "activity_ids": "act-1,act-2",
                "activity_types": "BUY,SELL",
                "asset_classes": "EQUITY",
                "data_source": "YAHOO",
                "symbol": "AAPL",
                "tags": "core",
            },
            "/api/v1/export/",
            {
                "accounts": "acc-1",
                "activityIds": "act-1,act-2",
                "activityTypes": "BUY,SELL",
                "assetClasses": "EQUITY",
                "dataSource": "YAHOO",
                "symbol": "AAPL",
                "tags": "core",
            },
        ),
        ("get_health", {}, "/api/v1/health/", {}),
        ("get_platforms", {}, "/api/v1/platforms/", {}),
        ("get_user_info", {}, "/api/v1/user/", {}),
        ("get_watchlist", {}, "/api/v1/watchlist/", {}),
        # /symbol/ routes take no trailing slash.
        (
            "lookup_symbols",
            {"query": "apple"},
            "/api/v1/symbol/lookup",
            {"query": "apple"},
        ),
        (
            "lookup_symbols",
            {"query": "S&P 500", "include_indices": True},
            "/api/v1/symbol/lookup",
            {"query": "S&P 500", "includeIndices": "true"},
        ),
    ],
)
async def test_read_tool_sends_get_and_returns_the_response(
    recorder, name, arguments, path, params
):
    mcp, requests, responses = recorder
    responses.append(httpx2.Response(200, json={"items": [1, 2]}))

    result = await call(mcp, name, arguments)

    [request] = requests
    assert request.method == "GET"
    assert request.url.path == path
    assert dict(request.url.params) == params
    assert request.headers["Authorization"] == "Bearer jwt"
    assert result.structured_content == {"items": [1, 2]}


@pytest.mark.asyncio
async def test_add_to_watchlist_posts_the_symbol(recorder):
    mcp, requests, _responses = recorder

    await call(mcp, "add_to_watchlist", {"data_source": "YAHOO", "symbol": "AAPL"})

    [request] = requests
    assert request.method == "POST"
    assert request.url.path == "/api/v1/watchlist"
    assert json.loads(request.content) == {"dataSource": "YAHOO", "symbol": "AAPL"}


@pytest.mark.asyncio
async def test_import_transactions_posts_the_payload_unchanged(recorder):
    mcp, requests, responses = recorder
    payload = {
        "activities": [
            {
                "currency": "USD",
                "dataSource": "YAHOO",
                "date": "2021-09-15T00:00:00.000Z",
                "fee": 0,
                "quantity": 2,
                "symbol": "AAPL",
                "type": "BUY",
                "unitPrice": 150.5,
            }
        ]
    }
    responses.append(httpx2.Response(201, json={"activities": [{"id": "new"}]}))

    result = await call(mcp, "import_transactions", {"data": payload})

    [request] = requests
    assert request.method == "POST"
    assert request.url.path == "/api/v1/import"
    assert json.loads(request.content) == payload
    assert result.structured_content == {"activities": [{"id": "new"}]}
