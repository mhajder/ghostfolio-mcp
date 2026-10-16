import logging
from typing import Annotated
from typing import Any

from fastmcp import FastMCP
from pydantic import Field

from ghostfolio_mcp.ghostfolio_client import get_ghostfolio_client
from ghostfolio_mcp.models import GhostfolioConfig
from ghostfolio_mcp.utils import quote_path_segment

logger = logging.getLogger(__name__)


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
                description="Type of activity: BUY, SELL, DIVIDEND, INTEREST, FEE, ITEM, LIABILITY"
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
            "destructiveHint": False,
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
                description="Optional new type: BUY, SELL, DIVIDEND, INTEREST, FEE, ITEM, LIABILITY",
            ),
        ] = None,
        symbol: Annotated[
            str | None,
            Field(
                default=None,
                description="Optional new symbol profile ID or actual ticker symbol",
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
                description="Optional new data source (e.g., 'YAHOO', 'COINGECKO', 'MANUAL')",
            ),
        ] = None,
        account_id: Annotated[
            str | None,
            Field(default=None, description="Optional new account ID"),
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
        `type`, `symbol`, `date`, `quantity`, `unitPrice`, `currency` and
        `dataSource` are required on every request even when they are not
        changing. Any left unset here (including `tags`) are backfilled from
        the activity's current state with a GET before the PUT, so you only
        need to pass the fields you actually want to change.

        Args:
            activity_id: The unique ID of the activity to update
            type: Optional new activity type
            symbol: Optional new symbol
            date: Optional new date
            quantity: Optional new quantity
            unit_price: Optional new price per unit
            currency: Optional new currency code
            data_source: Optional new data source
            account_id: Optional new account ID
            fee: Optional new fee amount
            comment: Optional new comment
            tags: Optional new list of tag IDs (replaces existing tags; omit to keep them)

        Returns:
            Dictionary containing the updated activity
        """
        async with get_ghostfolio_client(config) as client:
            current = await client.get(f"activities/{quote_path_segment(activity_id)}")
            current_symbol_profile = current.get("SymbolProfile") or current.get(
                "assetProfile", {}
            )
            current_tags = [
                tag["id"] for tag in current.get("tags") or [] if tag.get("id")
            ]

            # id, type, symbol, date, quantity, unitPrice, currency and
            # dataSource are required by Ghostfolio's UpdateOrderDto on every
            # request; fields the caller didn't override are backfilled from
            # the activity's current values.
            activity_data: dict[str, Any] = {
                "id": activity_id,
                "type": type if type is not None else current.get("type"),
                "symbol": (
                    symbol
                    if symbol is not None
                    else current_symbol_profile.get("symbol")
                ),
                "date": date if date is not None else current.get("date"),
                "quantity": (
                    quantity if quantity is not None else current.get("quantity")
                ),
                "unitPrice": (
                    unit_price if unit_price is not None else current.get("unitPrice")
                ),
                "currency": (
                    currency if currency is not None else current.get("currency")
                ),
                "dataSource": (
                    data_source
                    if data_source is not None
                    else current_symbol_profile.get("dataSource")
                ),
                "fee": fee if fee is not None else current.get("fee"),
                "tags": tags if tags is not None else current_tags,
            }
            if account_id is not None:
                activity_data["accountId"] = account_id
            elif current.get("accountId"):
                activity_data["accountId"] = current.get("accountId")
            if comment is not None:
                activity_data["comment"] = comment
            elif current.get("comment") is not None:
                activity_data["comment"] = current.get("comment")

            return await client.put(
                f"activities/{quote_path_segment(activity_id)}", data=activity_data
            )

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
