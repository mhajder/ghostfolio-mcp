#!/usr/bin/env python3
"""
Ghostfolio MCP Server

Provides a Model Context Protocol (MCP) server exposing tools that interact with the Ghostfolio API.
"""

import logging
import os
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from fastmcp.server.middleware.rate_limiting import SlidingWindowRateLimitingMiddleware
from fastmcp.server.transforms.search import BM25SearchTransform
from fastmcp.server.transforms.search import RegexSearchTransform

from ghostfolio_mcp.ghostfolio_client import get_ghostfolio_config_from_env
from ghostfolio_mcp.ghostfolio_client import get_transport_config_from_env
from ghostfolio_mcp.ghostfolio_tools import register_tools
from ghostfolio_mcp.sentry_init import init_sentry

# Load environment variables
load_dotenv()

# Initialize optional Sentry monitoring
init_sentry()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Get package version
try:
    __version__ = version("ghostfolio-mcp")
except PackageNotFoundError:
    __version__ = "0.0.1"

try:
    GHOSTFOLIO_CONFIG = get_ghostfolio_config_from_env()
    TRANSPORT_CONFIG = get_transport_config_from_env()
except Exception as e:
    logger.error(f"Invalid configuration: {e}")
    raise

# Create auth provider if bearer token is configured
auth_provider = None
if getattr(TRANSPORT_CONFIG, "http_bearer_token", None):
    auth_provider = StaticTokenVerifier(
        tokens={
            TRANSPORT_CONFIG.http_bearer_token: {
                "client_id": "authenticated-client",
                "scopes": ["read", "write"],
            }
        }
    )

# Initialize FastMCP server
mcp = FastMCP(
    name="Ghostfolio MCP Server",
    version=__version__,
    instructions=(
        "This MCP server exposes tools for interacting with the Ghostfolio API, supporting both read and write operations if not in read-only mode."
    ),
    auth=auth_provider,
)

# Register all tools
register_tools(mcp, GHOSTFOLIO_CONFIG)


def configure_component_visibility() -> None:
    """Apply server-level visibility transforms for read-only and disabled tags."""

    disabled_tags = getattr(GHOSTFOLIO_CONFIG, "disabled_tags", set())
    read_only_mode = getattr(GHOSTFOLIO_CONFIG, "read_only_mode", False)

    if read_only_mode:
        logger.info("Read-only mode is enabled - restricting to read-only components")
        mcp.enable(tags={"read-only"}, only=True)

    if disabled_tags:
        logger.info(
            "Disabled tags configured: %s - disabling matching components",
            disabled_tags,
        )
        mcp.disable(tags=disabled_tags)


def configure_tool_search() -> None:
    """Apply the optional FastMCP tool-search transform."""

    if not getattr(GHOSTFOLIO_CONFIG, "tool_search_enabled", False):
        return

    strategy = getattr(GHOSTFOLIO_CONFIG, "tool_search_strategy", "bm25")
    max_results = getattr(GHOSTFOLIO_CONFIG, "tool_search_max_results", 5)

    if strategy == "regex":
        mcp.add_transform(RegexSearchTransform(max_results=max_results))
    else:
        mcp.add_transform(BM25SearchTransform(max_results=max_results))

    logger.info(
        "Tool search is enabled - strategy=%s, max_results=%s",
        strategy,
        max_results,
    )


configure_component_visibility()
configure_tool_search()

# Optional rate limiting
if getattr(GHOSTFOLIO_CONFIG, "rate_limit_enabled", False):
    logger.info("Rate limiting is enabled - applying middleware")
    mcp.add_middleware(
        SlidingWindowRateLimitingMiddleware(
            max_requests=GHOSTFOLIO_CONFIG.rate_limit_max_requests,
            window_minutes=GHOSTFOLIO_CONFIG.rate_limit_window_minutes,
        )
    )


def main():
    # Basic validation
    if not all([GHOSTFOLIO_CONFIG.ghostfolio_url, GHOSTFOLIO_CONFIG.token]):
        logger.error(
            "Missing required Ghostfolio configuration (GHOSTFOLIO_URL or GHOSTFOLIO_TOKEN). Check your .env file."
        )
        raise SystemExit(1)

    logger.info(
        f"Starting Ghostfolio MCP Server at {GHOSTFOLIO_CONFIG.ghostfolio_url} ..."
    )

    # Choose transport based on configuration
    if TRANSPORT_CONFIG.transport_type == "sse":
        logger.info(
            f"Using HTTP SSE transport on {TRANSPORT_CONFIG.http_host}:{TRANSPORT_CONFIG.http_port}"
        )
        if TRANSPORT_CONFIG.http_bearer_token:
            logger.info("Bearer token authentication enabled for SSE transport")

        # Run with HTTP SSE transport
        mcp.run(
            transport="sse",
            host=TRANSPORT_CONFIG.http_host,
            port=TRANSPORT_CONFIG.http_port,
        )
    elif TRANSPORT_CONFIG.transport_type == "http":
        logger.info(
            f"Using HTTP Streamable transport on {TRANSPORT_CONFIG.http_host}:{TRANSPORT_CONFIG.http_port}"
        )
        if TRANSPORT_CONFIG.http_bearer_token:
            logger.info("Bearer token authentication enabled for Streamable transport")

        # Run with HTTP Streamable transport
        mcp.run(
            transport="http",
            host=TRANSPORT_CONFIG.http_host,
            port=TRANSPORT_CONFIG.http_port,
        )
    else:
        # Default to STDIO transport
        logger.info("Using STDIO transport")
        mcp.run()


if __name__ == "__main__":
    main()
