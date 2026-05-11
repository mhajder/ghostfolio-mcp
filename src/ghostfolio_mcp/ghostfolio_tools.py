"""
Ghostfolio MCP Tools
"""

import logging
from typing import Annotated
from typing import Any

import httpx
from fastmcp import FastMCP
from pydantic import Field

from ghostfolio_mcp.ghostfolio_client import get_ghostfolio_client
from ghostfolio_mcp.models import GhostfolioConfig

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP, config: GhostfolioConfig) -> None:
    """Register all Ghostfolio tools with the FastMCP server."""

    # =============================================================================
    # ACCOUNT ENDPOINTS
    # =============================================================================

    @mcp.tool(
        tags={"account", "balance", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_account_balances(
        account_id: Annotated[
            str,
            Field(description="Account ID to get balances for"),
        ],
    ) -> dict[str, Any]:
        """
        Get account balances for a specific account.

        Retrieves balance information for a specific account including
        current balance, currency, and balance history.

        Args:
            account_id: Account ID to get balances for

        Returns:
            Dictionary containing account balance information
        """
        async with get_ghostfolio_client(config) as client:
            return await client.get(f"account/{account_id}/balances")

    @mcp.tool(
        tags={"accounts", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_accounts() -> dict[str, Any]:
        """
        Get all accounts in your portfolio including account types and balances.

        Retrieves a list of all accounts in your portfolio including account
        types, balances, and account-specific information.

        Returns:
            Dictionary containing account information including accounts list and total value
        """
        async with get_ghostfolio_client(config) as client:
            return await client.get("account")

    @mcp.tool(
        tags={"account", "create"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def create_account(
        name: Annotated[
            str,
            Field(
                description="Name of the account (e.g., 'My Brokerage Account', 'Retirement Fund')"
            ),
        ],
        currency: Annotated[
            str,
            Field(
                description="Currency code for the account (e.g., 'USD', 'EUR', 'GBP')"
            ),
        ],
        balance: Annotated[
            float,
            Field(
                default=0.0,
                description="Initial balance for the account (defaults to 0)",
            ),
        ] = 0.0,
        comment: Annotated[
            str,
            Field(default="", description="Optional comment or note for the account"),
        ] = "",
        platform_id: Annotated[
            str | None,
            Field(
                default=None,
                description="Optional platform ID for the account (e.g., broker or exchange identifier)",
            ),
        ] = None,
        is_excluded: Annotated[
            bool,
            Field(
                default=False,
                description="Whether to exclude this account from portfolio calculations",
            ),
        ] = False,
    ) -> dict[str, Any]:
        """
        Create a new account in your portfolio.

        Creates a new account with the specified name, currency, and optional balance.
        This is useful for organizing your investments across different
        account types or platforms.

        Args:
            name: Account name (required)
            currency: Account currency (required, e.g., 'USD', 'EUR')
            balance: Initial balance for the account (defaults to 0)
            comment: Optional comment or note for the account
            platform_id: Optional platform ID for the account
            is_excluded: Whether to exclude this account from calculations

        Returns:
            Dictionary containing the created account information
        """
        async with get_ghostfolio_client(config) as client:
            account_data = {
                "name": name,
                "currency": currency,
                "balance": balance,
                "comment": comment,
                "isExcluded": is_excluded,
                "platformId": platform_id,
            }
            return await client.post("account", data=account_data)

    @mcp.tool(
        tags={"account", "delete"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    )
    async def delete_account(
        account_id: Annotated[
            str,
            Field(description="Account ID to delete (e.g., 'cb547e5c-..')"),
        ],
    ) -> dict[str, Any]:
        """
        Delete an existing account from your portfolio.

        Deletes an account specified by its ID. Be careful, this might delete
        associated transactions depending on backend rules!

        Args:
            account_id: Account ID to delete

        Returns:
            Dictionary containing the deletion status
        """
        async with get_ghostfolio_client(config) as client:
            return await client.delete(f"account/{account_id}")

    # =============================================================================
    # ASSET ENDPOINTS
    # =============================================================================

    @mcp.tool(
        tags={"asset", "profile", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_asset_profile(
        data_source: Annotated[
            str,
            Field(
                description="Data source for the symbol (e.g., 'YAHOO', 'COINGECKO', 'MANUAL')"
            ),
        ],
        symbol: Annotated[
            str,
            Field(description="Symbol/ticker of the asset (e.g., 'AAPL', 'BTC-USD')"),
        ],
    ) -> dict[str, Any]:
        """
        Get asset profile information for a specific symbol.

        Retrieves detailed profile information about an asset including
        company information, sector, industry, and other metadata.

        Args:
            data_source: Data source (e.g., 'YAHOO', 'COINGECKO', 'MANUAL')
            symbol: Symbol/ticker of the asset

        Returns:
            Dictionary containing asset profile information
        """
        async with get_ghostfolio_client(config) as client:
            return await client.get(f"asset/{data_source}/{symbol}")

    @mcp.tool(
        tags={"asset", "profile", "update"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def upsert_asset_profile(
        data_source: Annotated[
            str,
            Field(
                description="Data source for the symbol. Typically 'MANUAL' — Ghostfolio rejects profile-data writes for auto-fetched sources"
            ),
        ],
        symbol: Annotated[
            str,
            Field(
                description="Symbol/ticker of the asset. Permanent — renaming orphans associated activities and market data"
            ),
        ],
        name: Annotated[
            str,
            Field(description="Human-readable name for the asset"),
        ],
        currency: Annotated[
            str,
            Field(description="Currency code of the asset (e.g., 'USD', 'CHF', 'EUR')"),
        ],
        asset_class: Annotated[
            str,
            Field(
                description="Asset class: 'EQUITY', 'FIXED_INCOME', 'REAL_ESTATE', 'COMMODITY', 'LIQUIDITY' (cash), or 'ALTERNATIVE_INVESTMENT'. Note: Ghostfolio's enum does not include 'CASH' — use 'LIQUIDITY'"
            ),
        ],
        asset_sub_class: Annotated[
            str,
            Field(
                default="",
                description="Optional asset sub-class (e.g., 'MUTUALFUND', 'CASH', 'ETF')",
            ),
        ] = "",
    ) -> dict[str, Any]:
        """
        Create-or-update an asset profile.

        POSTs an empty profile-data record (idempotent — Ghostfolio returns
        HTTP 500 on both duplicate-create and some first-time-create paths
        while still persisting the record, so this tolerates 500). Then
        PATCHes metadata (name, currency, asset class, optional sub-class).
        PATCH is the source of truth — if the profile doesn't exist after
        the POST, PATCH will surface a 404. Calling twice with the same
        input yields the same end state.

        Args:
            data_source: Data source (typically 'MANUAL')
            symbol: Symbol/ticker of the asset
            name: Human-readable name
            currency: Currency code
            asset_class: One of the Ghostfolio enum values
            asset_sub_class: Optional sub-class

        Returns:
            Dictionary containing the final profile state from the PATCH response
        """
        async with get_ghostfolio_client(config) as client:
            # POST admin/profile-data/{source}/{symbol} creates the record but
            # Ghostfolio responds with HTTP 500 on both the duplicate-create
            # path and (observed against v3.2.0) some first-time-create paths,
            # while still persisting the record. Tolerate 500 here and treat
            # the subsequent PATCH as the source of truth — PATCH will 404
            # loudly if the profile genuinely does not exist.
            try:
                await client.post(f"admin/profile-data/{data_source}/{symbol}", data={})
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 500:
                    raise

            patch_payload: dict[str, Any] = {
                "name": name,
                "currency": currency,
                "assetClass": asset_class,
            }
            if asset_sub_class:
                patch_payload["assetSubClass"] = asset_sub_class

            return await client.patch(
                f"admin/profile-data/{data_source}/{symbol}", data=patch_payload
            )

    # =============================================================================
    # IMPORT ENDPOINTS
    # =============================================================================

    @mcp.tool(
        tags={"import"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def import_transactions(
        data: Annotated[
            dict[str, Any],
            Field(
                description="Transaction data in the format expected by Ghostfolio API. Should contain an 'activities' list. Each activity must have: 'currency', 'dataSource', 'date' (ISO-8601, e.g. 2021-09-15T00:00:00.000Z), 'quantity', 'symbol', 'type' (BUY, SELL, etc), 'unitPrice', and usually 'fee' (can be 0)."
            ),
        ],
    ) -> dict[str, Any]:
        """
        Import transactions into your portfolio. This is a write operation.

        Imports a batch of transactions (buy/sell orders) into your Ghostfolio
        portfolio. This is useful for bulk importing historical data or
        transactions from other platforms.

        Args:
            data: Transaction data. Must contain an 'activities' list with transaction objects including currency, dataSource, date (ISO-8601), fee, quantity, symbol, type, unitPrice.

        Returns:
            Dictionary containing import result
        """
        async with get_ghostfolio_client(config) as client:
            return await client.post("import", data=data)

    # =============================================================================
    # MARKET-DATA ENDPOINTS
    # =============================================================================

    @mcp.tool(
        tags={"market-data", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_market_data_for_asset(
        data_source: Annotated[
            str,
            Field(
                description="Data source for the symbol (e.g., 'YAHOO', 'COINGECKO', 'MANUAL')"
            ),
        ],
        symbol: Annotated[
            str,
            Field(description="Symbol/ticker of the asset (e.g., 'AAPL', 'BTC-USD')"),
        ],
    ) -> dict[str, Any]:
        """
        Get market data for a specific asset.

        Retrieves current market data for a specific symbol including price,
        volume, market cap, and other relevant market information.

        Args:
            data_source: Data source (e.g., 'YAHOO', 'COINGECKO', 'MANUAL')
            symbol: Symbol/ticker of the asset

        Returns:
            Dictionary containing market data for the specified symbol
        """
        async with get_ghostfolio_client(config) as client:
            return await client.get(f"market-data/{data_source}/{symbol}")

    @mcp.tool(
        tags={"market-data", "create"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def add_market_data_points(
        data_source: Annotated[
            str,
            Field(
                description="Data source for the symbol. Typically 'MANUAL' — Ghostfolio rejects market-data writes for auto-fetched sources like 'YAHOO' or 'COINGECKO'"
            ),
        ],
        symbol: Annotated[
            str,
            Field(
                description="Symbol/ticker of the asset (e.g., 'TRUE-UNLISTED', 'PILLAR3A-FINPENSION-X')"
            ),
        ],
        market_data: Annotated[
            list[dict[str, Any]],
            Field(
                description="List of market data points. Each entry must include 'date' (ISO 8601, e.g. '2026-04-30T00:00:00.000Z') and 'marketPrice' (numeric value of the asset at that date)"
            ),
        ],
    ) -> dict[str, Any]:
        """
        Add one or more market data points for a specific asset.

        Posts to the market-data endpoint for the given data source and
        symbol. Same (symbol, date) overwrites the existing point; passing
        the same input twice yields the same end state.

        Args:
            data_source: Data source (typically 'MANUAL')
            symbol: Symbol/ticker of the asset
            market_data: List of {date, marketPrice} entries

        Returns:
            Dictionary containing the upstream response
        """
        async with get_ghostfolio_client(config) as client:
            return await client.post(
                f"market-data/{data_source}/{symbol}",
                data={"marketData": market_data},
            )

    # =============================================================================
    # ORDER / ACTIVITY ENDPOINTS
    # =============================================================================

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
            return await client.get("order", params=params)

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
    ) -> dict[str, Any]:
        """
        Create a single new transaction/activity.
        """
        async with get_ghostfolio_client(config) as client:
            activity_data = {
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
            return await client.post("activities", data=activity_data)

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
            return await client.delete(f"activities/{activity_id}")

    # =============================================================================
    # PORTFOLIO ENDPOINTS
    # =============================================================================

    @mcp.tool(
        tags={"portfolio", "details", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_portfolio_details() -> dict[str, Any]:
        """
        Get comprehensive portfolio details including accounts, positions, and summary.

        Retrieves a complete overview of your portfolio including account
        information, current positions, performance summary, and portfolio metrics.

        Returns:
            Dictionary containing complete portfolio information including accounts, positions, and summary
        """
        async with get_ghostfolio_client(config) as client:
            return await client.get("portfolio/details")

    @mcp.tool(
        tags={"portfolio", "dividends", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_dividends(
        group_by: Annotated[
            str,
            Field(
                default="month",
                description="Grouping period for dividend data. Options: day, week, month, quarter, year",
            ),
        ] = "month",
        date_range: Annotated[
            str,
            Field(
                default="max",
                description="Time range for dividend data. Options: 1d, 1w, 1m, 3m, 6m, 1y, 2y, 5y, max",
            ),
        ] = "max",
    ) -> dict[str, Any]:
        """
        Get dividend data grouped by time period showing dividend payments and yield.

        Retrieves dividend income data grouped by the specified time period,
        showing dividend payments, yield, and income patterns over time.

        Args:
            group_by: Grouping period: day, week, month, quarter, year
            date_range: Time range for dividend data. Options: 1d, 1w, 1m, 3m, 6m, 1y, 2y, 5y, max

        Returns:
            Dictionary containing dividend data grouped by the specified period
        """
        async with get_ghostfolio_client(config) as client:
            return await client.get(
                "portfolio/dividends",
                params={"range": date_range, "groupBy": group_by},
            )

    @mcp.tool(
        tags={"portfolio", "holdings", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_portfolio_holdings(
        date_range: Annotated[
            str,
            Field(
                default="max",
                description="Time range for holdings data. Options: 1d, 1w, 1m, 3m, 6m, 1y, 2y, 5y, max",
            ),
        ] = "max",
    ) -> dict[str, Any]:
        """
        Get portfolio holdings and positions including allocations and asset breakdowns.

        Retrieves current portfolio holdings including positions, allocations,
        and asset breakdowns for the specified time period.

        Args:
            date_range: Time range for holdings data. Options: 1d, 1w, 1m, 3m, 6m, 1y, 2y, 5y, max

        Returns:
            Dictionary containing holdings, accounts, allocations, and range data
        """
        async with get_ghostfolio_client(config) as client:
            return await client.get("portfolio/holdings", params={"range": date_range})

    @mcp.tool(
        tags={"portfolio", "investments", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_investments(
        group_by: Annotated[
            str,
            Field(
                default="month",
                description="Grouping period for investment data. Options: day, week, month, quarter, year",
            ),
        ] = "month",
        date_range: Annotated[
            str,
            Field(
                default="max",
                description="Time range for investment data. Options: 1d, 1w, 1m, 3m, 6m, 1y, 2y, 5y, max",
            ),
        ] = "max",
    ) -> dict[str, Any]:
        """
        Get investment data grouped by time period showing cash flows and contributions.

        Retrieves investment activity data grouped by the specified time period,
        showing cash flows, contributions, and investment patterns over time.

        Args:
            group_by: Grouping period: day, week, month, quarter, year
            date_range: Time range for investment data. Options: 1d, 1w, 1m, 3m, 6m, 1y, 2y, 5y, max

        Returns:
            Dictionary containing investment data grouped by the specified period
        """
        async with get_ghostfolio_client(config) as client:
            return await client.get(
                "portfolio/investments",
                params={"range": date_range, "groupBy": group_by},
            )

    @mcp.tool(
        tags={"portfolio", "performance", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_portfolio_performance(
        date_range: Annotated[
            str,
            Field(
                default="max",
                description="Time range for performance data. Options: 1d, 1w, 1m, 3m, 6m, 1y, 2y, 5y, max",
            ),
        ] = "max",
    ) -> dict[str, Any]:
        """
        Get portfolio performance data including returns, benchmarks, and performance metrics.

        Retrieves comprehensive performance metrics for your portfolio including
        returns, benchmarks, and performance comparisons over the specified time period.

        Args:
            date_range: Time range for performance data. Options: 1d, 1w, 1m, 3m, 6m, 1y, 2y, 5y, max

        Returns:
            Dictionary containing performance metrics, returns, benchmarks, and range data
        """
        async with get_ghostfolio_client(config) as client:
            return await client.get(
                "portfolio/performance", params={"range": date_range}, api_version="v2"
            )

    @mcp.tool(
        tags={"portfolio", "positions", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_position(
        data_source: Annotated[
            str,
            Field(
                description="Data source for the symbol (e.g., 'YAHOO', 'COINGECKO', 'MANUAL')"
            ),
        ],
        symbol: Annotated[
            str,
            Field(description="Symbol/ticker of the asset (e.g., 'AAPL', 'BTC-USD')"),
        ],
    ) -> dict[str, Any]:
        """
        Get position details for a specific symbol from a data source.

        Retrieves detailed information about a specific position including
        current value, quantity, performance, and market data.

        Args:
            data_source: Data source (e.g., 'YAHOO', 'COINGECKO', 'MANUAL')
            symbol: Symbol/ticker of the asset

        Returns:
            Dictionary containing position details including symbol, quantity, value, and performance
        """
        async with get_ghostfolio_client(config) as client:
            return await client.get(f"portfolio/holding/{data_source}/{symbol}")

    # =============================================================================
    # SYMBOL ENDPOINTS
    # =============================================================================

    @mcp.tool(
        tags={"symbol", "data", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_symbol_data(
        data_source: Annotated[
            str,
            Field(
                description="Data source for the symbol (e.g., 'YAHOO', 'COINGECKO', 'MANUAL')"
            ),
        ],
        symbol: Annotated[
            str,
            Field(description="Symbol/ticker of the asset (e.g., 'AAPL', 'BTC')"),
        ],
    ) -> dict[str, Any]:
        """
        Get symbol data for a specific asset from a data source.

        Retrieves detailed information about a specific symbol including
        current price, market data, and asset information.

        Args:
            data_source: Data source (e.g., 'YAHOO', 'COINGECKO', 'MANUAL')
            symbol: Symbol/ticker of the asset

        Returns:
            Dictionary containing symbol data including price and market information
        """
        async with get_ghostfolio_client(config) as client:
            return await client.get(f"symbol/{data_source}/{symbol}")

    @mcp.tool(
        tags={"symbol", "historical", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_historical_data(
        data_source: Annotated[
            str,
            Field(
                description="Data source for the symbol (e.g., 'YAHOO', 'COINGECKO', 'MANUAL')"
            ),
        ],
        symbol: Annotated[
            str,
            Field(description="Symbol/ticker of the asset (e.g., 'AAPL', 'BTC-USD')"),
        ],
        date: Annotated[
            str,
            Field(description="Date in YYYY-MM-DD format for historical data"),
        ],
    ) -> dict[str, Any]:
        """
        Get historical data for a specific symbol on a specific date.

        Retrieves historical market data for a symbol on a specific date,
        including price and volume information.

        Args:
            data_source: Data source (e.g., 'YAHOO', 'COINGECKO', 'MANUAL')
            symbol: Symbol/ticker of the asset
            date: Date in YYYY-MM-DD format

        Returns:
            Dictionary containing historical data for the specified date
        """
        async with get_ghostfolio_client(config) as client:
            return await client.get(f"symbol/{data_source}/{symbol}/{date}")

    @mcp.tool(
        tags={"symbol", "lookup", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def lookup_symbols(
        query: Annotated[
            str,
            Field(
                description="Search query for symbol lookup. Can be company name, ticker symbol, or partial match"
            ),
        ],
        include_indices: Annotated[
            bool,
            Field(
                default=False, description="Include market indices in search results"
            ),
        ] = False,
    ) -> dict[str, Any]:
        """
        Search for symbols using a query string.

        Search for financial symbols, stocks, ETFs, and other assets using
        a text query. Optionally include market indices in the results.

        Args:
            query: Search query for symbol lookup
            include_indices: Include market indices in search results

        Returns:
            Dictionary containing search results with matching symbols
        """
        async with get_ghostfolio_client(config) as client:
            params = {"query": query}
            if include_indices:
                params["includeIndices"] = "true"
            return await client.get("symbol/lookup", params=params)

    # =============================================================================
    # USER ENDPOINTS
    # =============================================================================

    @mcp.tool(
        tags={"user", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_user_info() -> dict[str, Any]:
        """
        Get user information and settings.

        Retrieves information about the current user including settings,
        preferences, and account details.

        Returns:
            Dictionary containing user information and settings
        """
        async with get_ghostfolio_client(config) as client:
            return await client.get("user")

    # =============================================================================
    # SYSTEM ENDPOINTS
    # =============================================================================

    @mcp.tool(
        tags={"system", "health", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_health() -> dict[str, Any]:
        """
        Get system health status.

        Retrieves the health status of the Ghostfolio backend service.
        This is useful to verify if the server is up and running correctly.

        Returns:
            Dictionary containing health status information
        """
        async with get_ghostfolio_client(config) as client:
            return await client.get("health")

    @mcp.tool(
        tags={"system", "platforms", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_platforms() -> dict[str, Any]:
        """
        Get available platforms.

        Retrieves a list of all available platforms (brokers, exchanges, etc.)
        that can be used when tracking accounts or transactions.

        Returns:
            Dictionary containing available platforms
        """
        async with get_ghostfolio_client(config) as client:
            return await client.get("platforms")
