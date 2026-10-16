"""Tests for the activity write tools, including tags support.

Covers create_activity's optional `tags` passthrough and the new
update_activity tool, which mirrors update_account's backfill-from-GET
pattern because Ghostfolio's UpdateOrderDto also replaces the whole activity
record on every PUT.
"""

import json

import httpx2
import pytest

from tests.helpers import call


def current_activity(**overrides) -> dict:
    """An activity as GET /activities/:id returns it, with `overrides` applied."""
    activity = {
        "id": "act-1",
        "type": "BUY",
        "date": "2026-09-28T00:00:00.000Z",
        "quantity": 0.249,
        "unitPrice": 708.94,
        "currency": "USD",
        "fee": 0.0,
        "comment": "monthly buy",
        "accountId": "acc-1",
        "assetProfile": {
            "symbol": "VFIAX",
            "dataSource": "YAHOO",
            "currency": "USD",
        },
        "tags": [],
    }
    activity.update(overrides)
    return activity


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
    # Covers the fallback to a `SymbolProfile` key when `assetProfile` is absent.
    responses.append(
        httpx2.Response(
            200,
            json=current_activity(
                comment=None,
                assetProfile=None,
                SymbolProfile={"symbol": "VFIAX", "dataSource": "YAHOO"},
                tags=[
                    {"id": "a1bbe3e0-628b-4cdf-bf7c-78e0fe3a0b17", "name": "Retirement"}
                ],
            ),
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
            200, json=current_activity(tags=[{"id": "old-tag", "name": "Old"}])
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
            200, json=current_activity(tags=[{"id": "old-tag", "name": "Old"}])
        )
    )

    await call(mcp, "update_activity", {"activity_id": "act-1", "tags": []})

    body = json.loads(requests[1].content)
    assert body["tags"] == []


@pytest.mark.asyncio
async def test_update_activity_falls_back_to_asset_profile_currency(recorder):
    mcp, requests, responses = recorder
    # Order.currency is nullable in Ghostfolio's schema.
    responses.append(httpx2.Response(200, json=current_activity(currency=None)))

    await call(mcp, "update_activity", {"activity_id": "act-1", "fee": 1.5})

    body = json.loads(requests[1].content)
    assert body["currency"] == "USD"


@pytest.mark.asyncio
async def test_update_activity_reports_fields_it_cannot_backfill(recorder):
    mcp, requests, responses = recorder
    # A restricted view redacts quantity, fee and comment to null.
    responses.append(
        httpx2.Response(
            200, json=current_activity(quantity=None, fee=None, comment=None)
        )
    )

    with pytest.raises(Exception, match="Could not backfill quantity, fee, comment "):
        await call(mcp, "update_activity", {"activity_id": "act-1", "tags": []})
    assert [request.method for request in requests] == ["GET"]


@pytest.mark.asyncio
async def test_update_activity_uses_explicit_values_for_redacted_fields(recorder):
    mcp, requests, responses = recorder
    responses.append(
        httpx2.Response(
            200, json=current_activity(quantity=None, fee=None, comment=None)
        )
    )

    await call(
        mcp,
        "update_activity",
        {"activity_id": "act-1", "quantity": 2.0, "fee": 0.0, "comment": "kept"},
    )

    body = json.loads(requests[1].content)
    assert body["quantity"] == 2.0
    assert body["fee"] == 0.0
    assert body["comment"] == "kept"


@pytest.mark.asyncio
async def test_update_activity_requires_comment_when_it_is_redacted(recorder):
    mcp, requests, responses = recorder
    responses.append(
        httpx2.Response(
            200, json=current_activity(quantity=None, fee=None, comment=None)
        )
    )

    # Ghostfolio clears the comment on any update that omits it, so going
    # ahead with only quantity and fee would erase the hidden comment.
    with pytest.raises(Exception, match="Could not backfill comment "):
        await call(
            mcp,
            "update_activity",
            {"activity_id": "act-1", "quantity": 2.0, "fee": 0.0},
        )
    assert [request.method for request in requests] == ["GET"]


@pytest.mark.asyncio
async def test_update_activity_keeps_an_empty_comment_empty(recorder):
    mcp, requests, responses = recorder
    # A null comment next to a real quantity is genuinely empty, not redacted.
    responses.append(httpx2.Response(200, json=current_activity(comment=None)))

    await call(mcp, "update_activity", {"activity_id": "act-1", "fee": 1.5})

    body = json.loads(requests[1].content)
    assert "comment" not in body


@pytest.mark.asyncio
async def test_update_activity_without_asset_profile_reports_missing_fields(
    recorder,
):
    mcp, requests, responses = recorder
    responses.append(
        httpx2.Response(
            200,
            json=current_activity(assetProfile=None, SymbolProfile=None, currency=None),
        )
    )

    with pytest.raises(
        Exception, match="Could not backfill symbol, currency, data_source"
    ):
        await call(mcp, "update_activity", {"activity_id": "act-1", "fee": 1.5})
    assert [request.method for request in requests] == ["GET"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("arguments", "missing"),
    [
        ({"symbol": "AAPL"}, "data_source, currency"),
        ({"symbol": "AAPL", "data_source": "YAHOO"}, "currency"),
        # Same symbol on a different data source is a different asset too.
        ({"data_source": "MANUAL"}, "symbol, currency"),
    ],
)
async def test_update_activity_requires_the_whole_asset_when_it_changes(
    recorder, arguments, missing
):
    mcp, requests, responses = recorder
    responses.append(httpx2.Response(200, json=current_activity()))

    with pytest.raises(Exception, match=f"missing {missing} "):
        await call(mcp, "update_activity", {"activity_id": "act-1", **arguments})
    assert [request.method for request in requests] == ["GET"]


@pytest.mark.asyncio
async def test_update_activity_accepts_unchanged_asset_fields_alone(
    recorder,
):
    mcp, requests, responses = recorder
    responses.append(httpx2.Response(200, json=current_activity()))

    await call(
        mcp,
        "update_activity",
        {"activity_id": "act-1", "symbol": "VFIAX", "data_source": "YAHOO"},
    )

    body = json.loads(requests[1].content)
    assert body["symbol"] == "VFIAX"
    assert body["dataSource"] == "YAHOO"


@pytest.mark.asyncio
async def test_update_activity_matches_an_encoded_data_source(recorder):
    mcp, requests, responses = recorder
    # With ENABLE_FEATURE_SUBSCRIPTION Ghostfolio returns YAHOO as the first
    # 8 hex digits of its SHA-256.
    responses.append(
        httpx2.Response(
            200,
            json=current_activity(
                assetProfile={
                    "symbol": "VFIAX",
                    "dataSource": "4534c002",
                    "currency": "USD",
                }
            ),
        )
    )

    await call(
        mcp,
        "update_activity",
        {"activity_id": "act-1", "data_source": "YAHOO", "fee": 1.5},
    )

    assert [request.method for request in requests] == ["GET", "PUT"]


@pytest.mark.asyncio
async def test_update_activity_changes_the_whole_asset(recorder):
    mcp, requests, responses = recorder
    responses.append(httpx2.Response(200, json=current_activity()))

    await call(
        mcp,
        "update_activity",
        {
            "activity_id": "act-1",
            "symbol": "AAPL",
            "data_source": "YAHOO",
            "currency": "USD",
        },
    )

    body = json.loads(requests[1].content)
    assert body["symbol"] == "AAPL"
    assert body["dataSource"] == "YAHOO"
    assert body["currency"] == "USD"


@pytest.mark.asyncio
async def test_update_activity_keeps_current_account_by_default(recorder):
    mcp, requests, responses = recorder
    responses.append(httpx2.Response(200, json=current_activity()))

    await call(mcp, "update_activity", {"activity_id": "act-1", "fee": 1.5})

    body = json.loads(requests[1].content)
    assert body["accountId"] == "acc-1"
    assert body["comment"] == "monthly buy"


@pytest.mark.asyncio
async def test_update_activity_detaches_account_with_empty_account_id(recorder):
    mcp, requests, responses = recorder
    responses.append(httpx2.Response(200, json=current_activity()))

    await call(mcp, "update_activity", {"activity_id": "act-1", "account_id": ""})

    # Ghostfolio disconnects the account when accountId is absent.
    body = json.loads(requests[1].content)
    assert "accountId" not in body
