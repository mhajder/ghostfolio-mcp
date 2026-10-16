import hashlib
import logging
from typing import Annotated
from typing import Any

from fastmcp import FastMCP
from pydantic import Field

from ghostfolio_mcp.ghostfolio_client import get_ghostfolio_client
from ghostfolio_mcp.models import GhostfolioConfig
from ghostfolio_mcp.utils import quote_path_segment

logger = logging.getLogger(__name__)

# Fields Ghostfolio's UpdateOrderDto requires on every PUT /activities/:id,
# mapped to the update_activity parameter that supplies each one.
_REQUIRED_UPDATE_FIELDS = {
    "type": "type",
    "symbol": "symbol",
    "date": "date",
    "quantity": "quantity",
    "unitPrice": "unit_price",
    "currency": "currency",
    "dataSource": "data_source",
    "fee": "fee",
}


def _is_same_data_source(requested: str, current: str | None) -> bool:
    """
    Tell whether a requested data source names the activity's current one.

    With ENABLE_FEATURE_SUBSCRIPTION (e.g. ghostfol.io), Ghostfolio returns
    data sources other than MANUAL and GHOSTFOLIO encoded as the first 8 hex
    digits of their SHA-256, so a plain 'YAHOO' has to match that form too.
    """
    encoded = hashlib.sha256(requested.encode()).hexdigest()[:8]
    return current in (requested, encoded)


def register_activities_tools(mcp: FastMCP, config: GhostfolioConfig) -> None:
    """Register activity/order-related Ghostfolio tools with the FastMCP server."""

    @mcp.tool(
        tags={"portfolio", "orders", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_orders(
        account_id: Annotated[
            str | None,
            Field(
                default=None,
                description="Optional account ID to filter orders by specific account",
            ),
        ] = None,
    ) -> dict[str, Any]:
        """
        Get all activities/orders from your portfolio, optionally filtered by account.

        Retrieves a list of all buy/sell orders in your portfolio, optionally
        filtered by a specific account.

        Args:
            account_id: Optional account ID to filter orders by specific account

        Returns:
            Dictionary containing order data with activities and pagination
        """
        async with get_ghostfolio_client(config) as client:
            params = {"accounts": account_id} if account_id else None
            return await client.get("activities", params=params)

    @mcp.tool(
        tags={"portfolio", "activities", "create"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def create_activity(
        type: Annotated[
            str,
            Field(
                description="Type of activity: BUY, SELL, DIVIDEND, INTEREST, FEE, LIABILITY"
            ),
        ],
        symbol: Annotated[
            str, Field(description="Symbol profile ID or actual ticker symbol")
        ],
        date: Annotated[
            str,
            Field(
                description="Date in ISO 8601 format (e.g. 2026-05-09T00:00:00.000Z)"
            ),
        ],
        quantity: Annotated[float, Field(description="Number of shares/units")],
        unit_price: Annotated[float, Field(description="Price per unit")],
        currency: Annotated[
            str, Field(description="Currency code for the transaction")
        ],
        data_source: Annotated[
            str, Field(description="Data source (e.g., 'YAHOO', 'COINGECKO', 'MANUAL')")
        ],
        account_id: Annotated[
            str,
            Field(description="The account ID where this activity will be recorded"),
        ],
        fee: Annotated[
            float, Field(default=0.0, description="Optional fee amount")
        ] = 0.0,
        comment: Annotated[str, Field(default="", description="Optional comment")] = "",
        tags: Annotated[
            list[str] | None,
            Field(
                default=None,
                description=(
                    "Optional list of tag IDs to attach to this activity "
                    "(from get_tags). Omit for no tags."
                ),
            ),
        ] = None,
    ) -> dict[str, Any]:
        """
        Create a single new transaction/activity.
        """
        async with get_ghostfolio_client(config) as client:
            activity_data: dict[str, Any] = {
                "type": type,
                "symbol": symbol,
                "date": date,
                "quantity": quantity,
                "unitPrice": unit_price,
                "currency": currency,
                "dataSource": data_source,
                "accountId": account_id,
                "fee": fee,
                "comment": comment,
            }
            if tags is not None:
                activity_data["tags"] = tags
            return await client.post("activities", data=activity_data)

    @mcp.tool(
        tags={"portfolio", "activities", "update"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
        },
    )
    async def update_activity(
        activity_id: Annotated[
            str, Field(description="The unique ID of the activity to update")
        ],
        type: Annotated[
            str | None,
            Field(
                default=None,
                description="Optional new type: BUY, SELL, DIVIDEND, INTEREST, FEE, LIABILITY",
            ),
        ] = None,
        symbol: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Optional new ticker symbol. Changing the asset (symbol or "
                    "data_source) requires symbol, data_source and currency "
                    "together."
                ),
            ),
        ] = None,
        date: Annotated[
            str | None,
            Field(
                default=None,
                description="Optional new date in ISO 8601 format (e.g. 2026-05-09T00:00:00.000Z)",
            ),
        ] = None,
        quantity: Annotated[
            float | None,
            Field(default=None, description="Optional new number of shares/units"),
        ] = None,
        unit_price: Annotated[
            float | None, Field(default=None, description="Optional new price per unit")
        ] = None,
        currency: Annotated[
            str | None,
            Field(default=None, description="Optional new currency code"),
        ] = None,
        data_source: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Optional new data source (e.g., 'YAHOO', 'COINGECKO', "
                    "'MANUAL'). Changing it requires symbol and currency too."
                ),
            ),
        ] = None,
        account_id: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Optional new account ID. Pass an empty string to detach "
                    "the activity from its account."
                ),
            ),
        ] = None,
        fee: Annotated[
            float | None, Field(default=None, description="Optional new fee amount")
        ] = None,
        comment: Annotated[
            str | None, Field(default=None, description="Optional new comment")
        ] = None,
        tags: Annotated[
            list[str] | None,
            Field(
                default=None,
                description=(
                    "Optional new list of tag IDs (from get_tags) to replace this "
                    "activity's tags. Omit to leave existing tags unchanged; pass "
                    "an empty list to clear all tags."
                ),
            ),
        ] = None,
    ) -> dict[str, Any]:
        """
        Update an existing activity/transaction.

        Ghostfolio's update endpoint replaces the whole activity record, so
        `type`, `symbol`, `date`, `quantity`, `unitPrice`, `currency`,
        `dataSource` and `fee` are required on every request even when they
        are not changing. Any left unset here (including `tags`, `account_id`
        and `comment`) are backfilled from the activity's current state with a
        GET before the PUT, so you only need to pass the fields you actually
        want to change. If a required field can't be backfilled (Ghostfolio
        redacts `quantity` and `fee` in restricted views), pass it explicitly.
        A restricted view also redacts `comment`, and Ghostfolio clears the
        comment whenever the update carries none, so in that case `comment`
        is required too (pass an empty string to clear it).

        Ghostfolio identifies the asset by `dataSource` and `symbol` together,
        and the current `currency` belongs to that asset. So changing either
        `symbol` or `data_source` requires passing `symbol`, `data_source` and
        `currency` together; backfilling the rest from the old asset would
        attach the activity to the wrong asset profile or price it in the
        wrong currency. Ghostfolio ignores an asset change (without an error)
        when the resulting activity is a FEE, INTEREST or LIABILITY, or a BUY
        on the MANUAL data source; delete and re-create the activity instead.

        The GET and PUT are separate requests, so an edit made to the same
        activity in between (e.g. in the Ghostfolio UI) is overwritten for
        every field not passed here.

        Args:
            activity_id: The unique ID of the activity to update
            type: Optional new activity type
            symbol: Optional new symbol (changing it requires data_source and currency)
            date: Optional new date
            quantity: Optional new quantity
            unit_price: Optional new price per unit
            currency: Optional new currency code
            data_source: Optional new data source (changing it requires symbol and currency)
            account_id: Optional new account ID; an empty string detaches the account
            fee: Optional new fee amount
            comment: Optional new comment
            tags: Optional new list of tag IDs (replaces existing tags; omit to keep them)

        Returns:
            Dictionary containing the updated activity
        """
        path = f"activities/{quote_path_segment(activity_id)}"
        async with get_ghostfolio_client(config) as client:
            current = await client.get(path)
            asset_profile = (
                current.get("assetProfile") or current.get("SymbolProfile") or {}
            )

            asset_changes = (
                # Ghostfolio trims the symbol, so surrounding spaces are no change.
                symbol is not None and symbol.strip() != asset_profile.get("symbol")
            ) or (
                data_source is not None
                and not _is_same_data_source(
                    data_source, asset_profile.get("dataSource")
                )
            )
            if asset_changes:
                missing_asset_args = [
                    name
                    for name, value in (
                        ("symbol", symbol),
                        ("data_source", data_source),
                        ("currency", currency),
                    )
                    if value is None
                ]
                if missing_asset_args:
                    current_asset = (
                        "the current values belong to "
                        f"{asset_profile.get('symbol')!r} on "
                        f"{asset_profile.get('dataSource')!r}"
                        if asset_profile.get("symbol")
                        else "the activity has no current asset to keep them from"
                    )
                    raise ValueError(
                        "Changing the asset requires symbol, data_source and "
                        f"currency together; missing {', '.join(missing_asset_args)} "
                        f"({current_asset})"
                    )

            activity_data: dict[str, Any] = {
                "id": activity_id,
                "type": current.get("type"),
                "symbol": asset_profile.get("symbol"),
                "date": current.get("date"),
                "quantity": current.get("quantity"),
                "unitPrice": current.get("unitPrice"),
                # Order.currency is nullable; Ghostfolio itself falls back to
                # the asset profile's currency when it is unset.
                "currency": current.get("currency") or asset_profile.get("currency"),
                "dataSource": asset_profile.get("dataSource"),
                "fee": current.get("fee"),
                "accountId": current.get("accountId"),
                "comment": current.get("comment"),
                "tags": [
                    tag["id"] for tag in current.get("tags") or [] if tag.get("id")
                ],
            }
            overrides = {
                "type": type,
                "symbol": symbol,
                "date": date,
                "quantity": quantity,
                "unitPrice": unit_price,
                "currency": currency,
                "dataSource": data_source,
                "fee": fee,
                "accountId": account_id,
                "comment": comment,
                "tags": tags,
            }
            activity_data.update(
                {key: value for key, value in overrides.items() if value is not None}
            )

            # Ghostfolio's UpdateOrderDto requires these on every request, so a
            # missing one would only come back as an opaque 400.
            missing = [
                param
                for key, param in _REQUIRED_UPDATE_FIELDS.items()
                if activity_data[key] is None
            ]
            # Order.quantity is never null in Ghostfolio's database, so a null
            # one means the GET was redacted, and the comment with it. Since
            # Ghostfolio clears the comment on any update that omits it, a
            # backfilled null would silently erase it.
            if current.get("quantity") is None and comment is None:
                missing.append("comment")
            if missing:
                raise ValueError(
                    f"Could not backfill {', '.join(missing)} from activity "
                    f"{activity_id!r} (Ghostfolio returned no value, e.g. because "
                    "it is redacted in a restricted view); pass them explicitly"
                )

            # Ghostfolio detaches the account when accountId is absent or
            # empty, so only send a real one. A null comment here is a
            # genuinely empty one (a redacted one was caught above), and
            # omitting it keeps it empty.
            if not activity_data["accountId"]:
                del activity_data["accountId"]
            if activity_data["comment"] is None:
                del activity_data["comment"]

            return await client.put(path, data=activity_data)

    @mcp.tool(
        tags={"portfolio", "activities", "delete"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    )
    async def delete_activity(
        activity_id: Annotated[
            str, Field(description="The unique ID of the activity to delete")
        ],
    ) -> dict[str, Any]:
        """
        Delete a single activity/transaction by its ID.
        """
        async with get_ghostfolio_client(config) as client:
            return await client.delete(f"activities/{quote_path_segment(activity_id)}")
