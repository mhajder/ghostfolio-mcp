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

import httpx2
import pytest

from tests.helpers import call


@pytest.mark.asyncio
async def test_update_account_backfills_required_fields_from_current_account(
    recorder,
):
    mcp, requests, responses = recorder
    responses.append(
        httpx2.Response(
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
        httpx2.Response(
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
async def test_update_account_reports_fields_it_cannot_backfill(recorder):
    mcp, requests, _responses = recorder
    # Ghostfolio answers GET /account/:id for an unknown id with an empty body.

    with pytest.raises(Exception, match="Could not backfill name, currency "):
        await call(mcp, "update_account", {"account_id": "acc-1", "comment": "x"})
    assert [request.method for request in requests] == ["GET"]


@pytest.mark.asyncio
async def test_update_account_keeps_a_missing_platform_as_none(recorder):
    mcp, requests, responses = recorder
    # platformId is nullable (an account without a platform), so a null one
    # is sent back rather than reported as missing.
    responses.append(
        httpx2.Response(
            200,
            json={"id": "acc-1", "name": "Cash", "currency": "USD", "platformId": None},
        )
    )

    await call(mcp, "update_account", {"account_id": "acc-1", "name": "Wallet"})

    body = json.loads(requests[1].content)
    assert body == {
        "id": "acc-1",
        "name": "Wallet",
        "currency": "USD",
        "platformId": None,
    }


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
        httpx2.Response(
            400,
            json={
                "message": ["currency must be a valid currency code"],
                "error": "Bad Request",
                "statusCode": 400,
            },
        )
    )

    with pytest.raises(
        httpx2.HTTPStatusError, match="currency must be a valid currency code"
    ):
        await call(
            mcp, "create_account_balance", {"account_id": "acc-1", "balance": 100.0}
        )


@pytest.mark.asyncio
async def test_failed_write_error_body_is_truncated_when_large(recorder):
    mcp, _requests, responses = recorder
    responses.append(httpx2.Response(400, text="x" * 5000))

    with pytest.raises(httpx2.HTTPStatusError, match=r"\(truncated\)") as exc_info:
        await call(
            mcp, "create_account_balance", {"account_id": "acc-1", "balance": 100.0}
        )

    assert len(str(exc_info.value)) < 3000


@pytest.mark.asyncio
async def test_get_accounts_lists_every_account(recorder):
    mcp, requests, responses = recorder
    responses.append(httpx2.Response(200, json={"accounts": [{"id": "acc-1"}]}))

    result = await call(mcp, "get_accounts", {})

    assert [(r.method, r.url.path) for r in requests] == [("GET", "/api/v1/account/")]
    assert result.structured_content == {"accounts": [{"id": "acc-1"}]}


@pytest.mark.asyncio
async def test_create_account_sends_defaults_for_optional_fields(recorder):
    mcp, requests, _responses = recorder

    await call(mcp, "create_account", {"name": "Broker", "currency": "EUR"})

    [request] = requests
    assert request.method == "POST"
    assert request.url.path == "/api/v1/account"
    assert json.loads(request.content) == {
        "name": "Broker",
        "currency": "EUR",
        "balance": 0.0,
        "comment": "",
        "platformId": None,
    }


@pytest.mark.asyncio
async def test_create_account_forwards_every_field(recorder):
    mcp, requests, _responses = recorder

    await call(
        mcp,
        "create_account",
        {
            "name": "Broker",
            "currency": "USD",
            "balance": 250.5,
            "comment": "main",
            "platform_id": "platform-1",
        },
    )

    assert json.loads(requests[0].content) == {
        "name": "Broker",
        "currency": "USD",
        "balance": 250.5,
        "comment": "main",
        "platformId": "platform-1",
    }


@pytest.mark.asyncio
async def test_transfer_account_balance_posts_both_accounts_and_amount(recorder):
    mcp, requests, _responses = recorder

    await call(
        mcp,
        "transfer_account_balance",
        {"account_id_from": "acc-1", "account_id_to": "acc-2", "balance": 75.0},
    )

    [request] = requests
    assert request.method == "POST"
    assert request.url.path == "/api/v1/account/transfer-balance"
    assert json.loads(request.content) == {
        "accountIdFrom": "acc-1",
        "accountIdTo": "acc-2",
        "balance": 75.0,
    }
