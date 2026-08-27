import logging
from datetime import UTC
from datetime import datetime
from typing import Annotated
from typing import Any

from fastmcp import FastMCP
from pydantic import Field

from ghostfolio_mcp.ghostfolio_client import get_ghostfolio_client
from ghostfolio_mcp.models import GhostfolioConfig
from ghostfolio_mcp.utils import quote_path_segment

logger = logging.getLogger(__name__)


def register_accounts_tools(mcp: FastMCP, config: GhostfolioConfig) -> None:
    """Register account-related Ghostfolio tools with the FastMCP server."""

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
            return await client.get(
                f"account/{quote_path_segment(account_id)}/balances"
            )

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
    ) -> dict[str, Any]:
        """
        Create a new account in your portfolio.

        Creates a new account with the specified name, currency, and optional balance.
        This is useful for organizing your investments across different
        account types or platforms.

        Note: current Ghostfolio versions have no boolean "excluded" flag on an
        account - exclusion from analysis is done by tagging the account, which
        is outside this tool's scope.

        Args:
            name: Account name (required)
            currency: Account currency (required, e.g., 'USD', 'EUR')
            balance: Initial balance for the account (defaults to 0)
            comment: Optional comment or note for the account
            platform_id: Optional platform ID for the account

        Returns:
            Dictionary containing the created account information
        """
        async with get_ghostfolio_client(config) as client:
            account_data = {
                "name": name,
                "currency": currency,
                "balance": balance,
                "comment": comment,
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
            return await client.delete(f"account/{quote_path_segment(account_id)}")

    @mcp.tool(
        tags={"account", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_account_details(
        account_id: Annotated[
            str,
            Field(description="Account ID to retrieve details for"),
        ],
    ) -> dict[str, Any]:
        """
        Get details for a specific account.

        Args:
            account_id: The unique ID of the account to fetch

        Returns:
            Dictionary containing the detailed account profile
        """
        async with get_ghostfolio_client(config) as client:
            return await client.get(f"account/{quote_path_segment(account_id)}")

    @mcp.tool(
        tags={"account", "update"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def update_account(
        account_id: Annotated[
            str,
            Field(description="Account ID to update"),
        ],
        name: Annotated[
            str | None,
            Field(default=None, description="Optional new name of the account"),
        ] = None,
        currency: Annotated[
            str | None,
            Field(
                default=None,
                description="Optional new currency code for the account (e.g., 'USD', 'EUR')",
            ),
        ] = None,
        balance: Annotated[
            float | None,
            Field(default=None, description="Optional new balance for the account"),
        ] = None,
        comment: Annotated[
            str | None,
            Field(
                default=None,
                description="Optional new comment or note for the account",
            ),
        ] = None,
        platform_id: Annotated[
            str | None,
            Field(
                default=None,
                description="Optional new platform ID for the account",
            ),
        ] = None,
    ) -> dict[str, Any]:
        """
        Update settings or details of an existing account.

        Ghostfolio's update endpoint replaces the whole account record, so
        `name`, `currency` and `platform_id` are required on every request even
        when they are not changing. Any left unset here are backfilled from the
        account's current state with a GET before the PUT, so you only need to
        pass the fields you actually want to change.

        Setting `balance` here applies it as *today's* entry in the account's
        balance history (the same series `get_account_balances` returns and
        `get_portfolio_holdings` derives its cash figure from) - it is not a
        separate stale field. Use create_account_balance to set the balance
        for a specific past date instead of today.

        Args:
            account_id: The unique ID of the account to update
            name: Optional new account name
            currency: Optional new account currency
            balance: Optional new cash balance, recorded as today's balance-history entry
            comment: Optional new note/comment
            platform_id: Optional new platform ID

        Returns:
            Dictionary containing the updated account status
        """
        async with get_ghostfolio_client(config) as client:
            current = await client.get(f"account/{quote_path_segment(account_id)}")

            # id, name, currency and platformId are required by Ghostfolio's
            # UpdateAccountDto on every request; fields the caller didn't
            # override are backfilled from the account's current values.
            account_data: dict[str, Any] = {
                "id": account_id,
                "name": name if name is not None else current.get("name"),
                "currency": (
                    currency if currency is not None else current.get("currency")
                ),
                "platformId": (
                    platform_id
                    if platform_id is not None
                    else current.get("platformId")
                ),
            }
            if balance is not None:
                account_data["balance"] = balance
            if comment is not None:
                account_data["comment"] = comment

            return await client.put(
                f"account/{quote_path_segment(account_id)}", data=account_data
            )

    @mcp.tool(
        tags={"account", "transfer"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def transfer_account_balance(
        account_id_from: Annotated[
            str,
            Field(description="The source account ID to transfer cash from"),
        ],
        account_id_to: Annotated[
            str,
            Field(description="The target account ID to transfer cash to"),
        ],
        balance: Annotated[
            float,
            Field(description="The amount of cash to transfer"),
        ],
    ) -> dict[str, Any]:
        """
        Transfer cash balances between two accounts.

        Args:
            account_id_from: Source account ID
            account_id_to: Target account ID
            balance: Amount to transfer

        Returns:
            Dictionary containing the status/result of the transfer.
        """
        async with get_ghostfolio_client(config) as client:
            payload = {
                "accountIdFrom": account_id_from,
                "accountIdTo": account_id_to,
                "balance": balance,
            }
            return await client.post("account/transfer-balance", data=payload)

    @mcp.tool(
        tags={"account", "balance", "create"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def create_account_balance(
        account_id: Annotated[
            str,
            Field(description="Account ID to record a balance entry for"),
        ],
        balance: Annotated[
            float,
            Field(description="Balance value to record for the given date"),
        ],
        date: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "ISO-8601 date for this balance entry, e.g. '2026-08-27'. "
                    "Defaults to today."
                ),
            ),
        ] = None,
    ) -> dict[str, Any]:
        """
        Set an account's balance for a specific date in its balance history.

        This writes directly to the balance-history series that
        get_account_balances returns and that get_portfolio_holdings derives
        its cash figure from - it is not the same as the account's summary
        balance field. Calling this again for the same account and date
        updates that entry instead of duplicating it, so setting today's
        balance is just this call with `date` omitted.

        The balance is recorded in the account's own currency; Ghostfolio's
        API does not accept a separate currency for this endpoint.

        Args:
            account_id: Account ID to record a balance entry for
            balance: Balance value for the given date
            date: Optional ISO-8601 date (defaults to today)

        Returns:
            Dictionary containing the created/updated balance-history entry
        """
        async with get_ghostfolio_client(config) as client:
            payload = {
                "accountId": account_id,
                "balance": balance,
                "date": date or datetime.now(UTC).strftime("%Y-%m-%d"),
            }
            return await client.post("account-balance", data=payload)

    @mcp.tool(
        tags={"account", "balance", "delete"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    )
    async def delete_account_balance(
        balance_id: Annotated[
            str,
            Field(
                description=(
                    "ID of the balance-history entry to delete, from "
                    "get_account_balances (not the account ID)"
                )
            ),
        ],
    ) -> dict[str, Any]:
        """
        Delete a single entry from an account's balance history.

        Args:
            balance_id: ID of the balance-history entry to delete

        Returns:
            Dictionary containing the deleted balance-history entry
        """
        async with get_ghostfolio_client(config) as client:
            return await client.delete(
                f"account-balance/{quote_path_segment(balance_id)}"
            )
