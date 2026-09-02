import logging
from typing import Annotated
from typing import Any

import httpx2
from fastmcp import FastMCP
from pydantic import Field

from ghostfolio_mcp.ghostfolio_client import get_ghostfolio_client
from ghostfolio_mcp.models import GhostfolioConfig
from ghostfolio_mcp.utils import quote_path_segment

logger = logging.getLogger(__name__)


def register_assets_tools(mcp: FastMCP, config: GhostfolioConfig) -> None:
    """Register asset-related Ghostfolio tools with the FastMCP server."""

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
            return await client.get(
                f"asset/{quote_path_segment(data_source)}/{quote_path_segment(symbol)}"
            )

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
            profile_path = (
                f"admin/profile-data/{quote_path_segment(data_source)}"
                f"/{quote_path_segment(symbol)}"
            )
            # POST admin/profile-data/{source}/{symbol} creates the record but
            # Ghostfolio responds with HTTP 500 on both the duplicate-create
            # path and (observed against v3.2.0) some first-time-create paths,
            # while still persisting the record. Tolerate 500 here and treat
            # the subsequent PATCH as the source of truth — PATCH will 404
            # loudly if the profile genuinely does not exist.
            try:
                await client.post(profile_path, data={})
            except httpx2.HTTPStatusError as exc:
                if exc.response.status_code != 500:
                    raise

            patch_payload: dict[str, Any] = {
                "name": name,
                "currency": currency,
                "assetClass": asset_class,
            }
            if asset_sub_class:
                patch_payload["assetSubClass"] = asset_sub_class

            return await client.patch(profile_path, data=patch_payload)

    @mcp.tool(
        tags={"asset", "profile", "delete"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    )
    async def delete_asset_profile(
        data_source: Annotated[
            str,
            Field(
                description="Data source for the symbol. Typically 'MANUAL' — Ghostfolio rejects profile-data deletes for auto-fetched sources"
            ),
        ],
        symbol: Annotated[
            str,
            Field(description="Symbol/ticker of the asset to delete"),
        ],
    ) -> dict[str, Any]:
        """
        Delete an asset profile.

        Removes the profile-data record for the given data source and symbol.
        Be careful, this might delete associated activities and market data
        depending on backend rules!

        Args:
            data_source: Data source (typically 'MANUAL')
            symbol: Symbol/ticker of the asset to delete

        Returns:
            Dictionary containing the deletion status
        """
        async with get_ghostfolio_client(config) as client:
            return await client.delete(
                f"admin/profile-data/{quote_path_segment(data_source)}"
                f"/{quote_path_segment(symbol)}"
            )
