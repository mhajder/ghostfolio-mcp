# Ghostfolio MCP Server

Ghostfolio MCP Server is a Python-based Model Context Protocol (MCP) server designed to provide advanced, programmable access to Ghostfolio portfolio management and financial data. It exposes a modern API for querying, analyzing, and managing your investment portfolio through Ghostfolio's comprehensive features. The server supports both read and write operations, robust security features, and is suitable for integration with automation tools, financial dashboards, and custom portfolio management applications.

## Features

### Core Features

- Query portfolio performance, holdings, and positions with flexible time ranges
- Retrieve comprehensive investment data including dividends, returns, and allocations
- Access detailed market data, asset profiles, and historical price information
- Monitor portfolio metrics, benchmarks, and performance comparisons
- Track orders, transactions, and account balances across multiple accounts
- Search and lookup financial symbols, stocks, ETFs, and other assets
- Get user information, settings, and account details

### Management Operations

- Create and manage investment accounts with different currencies and platforms
- Import transactions and historical data from other platforms
- Configure read-only mode to restrict all write operations for safe monitoring
- Support for bulk transaction imports and portfolio data management

### Advanced Capabilities

- Rate limiting and API security features
- Real-time portfolio monitoring and performance tracking
- Comprehensive logging and audit trails
- SSL/TLS support and configurable timeouts
- Extensible with custom middlewares and tag-based tool filtering

## Installation

### Prerequisites

- Python 3.11 or higher
- Access to a Ghostfolio instance
- Valid Ghostfolio API token

### Quick Install from PyPI

The easiest way to get started is to install from PyPI:

```sh
# Using UV (recommended)
uvx ghostfolio-mcp

# Or using pip
pip install ghostfolio-mcp
```

Remember to configure the environment variables for your Ghostfolio instance before running the server:

```sh
# Create environment configuration
export GHOSTFOLIO_URL=https://domain.tld:3333
export GHOSTFOLIO_TOKEN=your-ghostfolio-token
```

For more details, visit: https://pypi.org/project/ghostfolio-mcp/

### Install from Source

1. Clone the repository:

```sh
git clone https://github.com/mhajder/ghostfolio-mcp.git
cd ghostfolio-mcp
```

2. Install dependencies:

```sh
# Using UV (recommended)
uv sync

# Or using pip
pip install -e .
```

3. Configure environment variables:

```sh
cp .env.example .env
# Edit .env with your Ghostfolio URL and token
```

4. Run the server:

```sh
# Using UV
uv run python run_server.py

# Or directly with Python
python run_server.py

# Or using the installed script
ghostfolio-mcp
```

### Development Setup

For development with additional tools:

```sh
# Clone and install with development dependencies
git clone https://github.com/mhajder/ghostfolio-mcp.git
cd ghostfolio-mcp
uv sync --group dev

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/

# Run linting and formatting
uv run ruff check .
uv run ruff format .

# Setup pre-commit hooks
uv run pre-commit install
```

## Configuration

### Environment Variables

```env
# Ghostfolio Connection Details
GHOSTFOLIO_URL=https://domain.tld:3333
GHOSTFOLIO_TOKEN=your-ghostfolio-token

# SSL Configuration
GHOSTFOLIO_VERIFY_SSL=true
GHOSTFOLIO_TIMEOUT=30

# Read-Only Mode
# Set READ_ONLY_MODE true to disable all write operations (put, post, delete)
READ_ONLY_MODE=false

# Disabled Tags
# Comma-separated list of tags to disable tools for (empty by default)
# Example: GHOSTFOLIO_DISABLED_TAGS=portfolio,symbol
GHOSTFOLIO_DISABLED_TAGS=

# Logging Configuration
LOG_LEVEL=INFO

# Rate Limiting (requests per minute)
# Set RATE_LIMIT_ENABLED true to enable rate limiting
RATE_LIMIT_ENABLED=false
RATE_LIMIT_MAX_REQUESTS=100
RATE_LIMIT_WINDOW_MINUTES=1

# Sentry Error Tracking (Optional)
# Set SENTRY_DSN to enable error tracking and performance monitoring
# SENTRY_DSN=https://your-key@o12345.ingest.us.sentry.io/6789
# Optional Sentry configuration
# SENTRY_TRACES_SAMPLE_RATE=1.0
# SENTRY_SEND_DEFAULT_PII=true
# SENTRY_ENVIRONMENT=production
# SENTRY_RELEASE=1.2.3
# SENTRY_PROFILE_SESSION_SAMPLE_RATE=1.0
# SENTRY_PROFILE_LIFECYCLE=trace
# SENTRY_ENABLE_LOGS=true

# MCP Transport Configuration
# Transport type: 'stdio' (default), 'sse' (Server-Sent Events), or 'http' (HTTP Streamable)
MCP_TRANSPORT=stdio

# HTTP Transport Settings (used when MCP_TRANSPORT=sse or MCP_TRANSPORT=http)
# Host to bind the HTTP server (default: 0.0.0.0 for all interfaces)
MCP_HTTP_HOST=0.0.0.0
# Port to bind the HTTP server (default: 8000)
MCP_HTTP_PORT=8000
# Optional bearer token for authentication (leave empty for no auth)
MCP_HTTP_BEARER_TOKEN=
```

### Sentry Error Tracking & Monitoring (Optional)

The server optionally supports **Sentry** for error tracking, performance monitoring, and debugging. Sentry integration is completely optional and only initialized if configured.

#### Installation

To enable Sentry monitoring, install the optional dependency:

```sh
# Using UV (recommended)
uv sync --extra sentry
```

#### Configuration

Enable Sentry by setting the `SENTRY_DSN` environment variable in your `.env` file:

```env
# Required: Sentry DSN for your project
SENTRY_DSN=https://your-key@o12345.ingest.us.sentry.io/6789

# Optional: Performance monitoring sample rate (0.0-1.0, default: 1.0)
SENTRY_TRACES_SAMPLE_RATE=1.0

# Optional: Include personally identifiable information (default: true)
SENTRY_SEND_DEFAULT_PII=true

# Optional: Environment name (e.g., "production", "staging")
SENTRY_ENVIRONMENT=production

# Optional: Release version (auto-detected from package if not set)
SENTRY_RELEASE=1.2.2

# Optional: Profiling - continuous profiling sample rate (0.0-1.0, default: 1.0)
SENTRY_PROFILE_SESSION_SAMPLE_RATE=1.0

# Optional: Profiling - lifecycle mode for profiling (default: "trace")
# Options: "all", "continuation", "trace"
SENTRY_PROFILE_LIFECYCLE=trace

# Optional: Enable log capture as breadcrumbs and events (default: true)
SENTRY_ENABLE_LOGS=true
```

#### Features

When enabled, Sentry automatically captures:

- **Exceptions & Errors**: All unhandled exceptions with full context
- **Performance Metrics**: Request/response times and traces
- **MCP Integration**: Detailed MCP server activity and interactions
- **Logs & Breadcrumbs**: Application logs and event trails for debugging
- **Context Data**: Environment, client info, and request parameters

#### Getting a Sentry DSN

1. Create a free account at [sentry.io](https://sentry.io)
2. Create a new Python project
3. Copy your DSN from the project settings
4. Set it in your `.env` file

#### Disabling Sentry

Sentry is completely optional. If you don't set `SENTRY_DSN`, the server will run normally without any Sentry integration, and no monitoring data will be collected.

## Available Tools

### Account Management Tools

- `get_accounts`: Get all accounts in your portfolio including account types and balances
- `get_account_balances`: Get account balances for a specific account
- `create_account`: Create a new account in your portfolio

### Portfolio Analysis Tools

- `get_portfolio_performance`: Get portfolio performance data including returns, benchmarks, and performance metrics
- `get_portfolio_holdings`: Get portfolio holdings and positions including allocations and asset breakdowns
- `get_portfolio_details`: Get comprehensive portfolio details including accounts, positions, and summary
- `get_position`: Get position details for a specific symbol from a data source
- `get_investments`: Get investment data grouped by time period showing cash flows and contributions
- `get_dividends`: Get dividend data grouped by time period showing dividend payments and yield
- `get_orders`: Get all orders from your portfolio, optionally filtered by account

### Market Data & Symbol Tools

- `get_market_data_admin`: Get overview of market data loaded in your Ghostfolio instance
- `get_market_data`: Get market data for a specific symbol from a data source
- `get_market_data_for_asset`: Get market data for a specific asset
- `get_symbol_data`: Get symbol data for a specific asset from a data source
- `get_historical_data`: Get historical data for a specific symbol on a specific date
- `lookup_symbols`: Search for symbols using a query string

### Asset Information Tools

- `get_asset_profile`: Get asset profile information for a specific symbol

### Data Import Tools

- `import_transactions`: Import transactions into your portfolio (write operation)

### User Management Tools

- `get_user_info`: Get user information and settings

## Security & Safety Features

### Read-Only Mode

The server supports a read-only mode that disables all write operations for safe monitoring:

```env
READ_ONLY_MODE=true
```

When enabled, this mode prevents any modifications to your portfolio data while still allowing full read access to all information.

### Tag-Based Tool Filtering

You can disable specific categories of tools by setting disabled tags:

```env
GHOSTFOLIO_DISABLED_TAGS=portfolio,symbol,import
```

Available tags include:
- `portfolio` - Portfolio analysis and performance tools
- `symbol` - Symbol lookup and data tools
- `account` - Account management tools
- `import` - Data import tools
- `admin` - Administrative tools
- `market-data` - Market data tools
- `asset` - Asset profile tools
- `user` - User information tools

### Rate Limiting

The server supports rate limiting to control API usage and prevent abuse. If enabled, requests are limited per client using a sliding window algorithm.

Enable rate limiting by setting the following environment variables in your `.env` file:

```env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_MAX_REQUESTS=100   # Maximum requests allowed per window
RATE_LIMIT_WINDOW_MINUTES=1   # Window size in minutes
```

If `RATE_LIMIT_ENABLED` is set to `true`, the server will apply rate limiting middleware. Adjust `RATE_LIMIT_MAX_REQUESTS` and `RATE_LIMIT_WINDOW_MINUTES` as needed for your environment.

### SSL/TLS Configuration

The server supports SSL certificate verification and custom timeout settings:

```env
GHOSTFOLIO_VERIFY_SSL=true    # Enable SSL certificate verification
GHOSTFOLIO_TIMEOUT=30         # Connection timeout in seconds
```

### Transport Configuration

The server supports multiple transport protocols for different deployment scenarios:

#### STDIO Transport (Default)

The default transport uses standard input/output for communication. This is ideal for local usage and integration with tools that communicate via stdin/stdout:

```env
MCP_TRANSPORT=stdio
```

#### HTTP SSE Transport (Server-Sent Events)

For network-based deployments, you can use HTTP with Server-Sent Events. This allows the MCP server to be accessed over HTTP with real-time streaming:

```env
MCP_TRANSPORT=sse
MCP_HTTP_HOST=0.0.0.0        # Bind to all interfaces (or specific IP)
MCP_HTTP_PORT=8000           # Port to listen on
MCP_HTTP_BEARER_TOKEN=your-secret-token  # Optional authentication token
```

When using SSE transport with a bearer token, clients must include the token in their requests:

```bash
curl -H "Authorization: Bearer your-secret-token" http://localhost:8000/sse
```

#### HTTP Streamable Transport

The HTTP Streamable transport provides HTTP-based communication with request/response streaming. This is ideal for web integrations and tools that need HTTP endpoints:

```env
MCP_TRANSPORT=http
MCP_HTTP_HOST=0.0.0.0        # Bind to all interfaces (or specific IP)
MCP_HTTP_PORT=8000           # Port to listen on
MCP_HTTP_BEARER_TOKEN=your-secret-token  # Optional authentication token
```

When using streamable transport with a bearer token:

```sh
curl -H "Authorization: Bearer your-secret-token" \
     -H "Accept: application/json, text/event-stream" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
     http://localhost:8000/mcp
```

**Note**: The HTTP transport requires proper JSON-RPC formatting with `jsonrpc` and `id` fields. The server may also require session initialization for some operations.

## Data Sources

Ghostfolio supports multiple data sources for market data and symbols:

- **YAHOO** - Yahoo Finance data source
- **COINGECKO** - CoinGecko for cryptocurrency data
- **MANUAL** - Manually entered data
- And other configured data sources in your Ghostfolio instance

When using tools that require a data source parameter, specify the appropriate source for your asset type.

## Using Docker

A Docker images are available on GitHub Packages for easy deployment.

```sh
# Normal STDIO image
docker pull ghcr.io/mhajder/ghostfolio-mcp:latest

# MCPO image for usage with Open WebUI
docker pull ghcr.io/mhajder/ghostfolio-mcpo:latest
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and ensure code quality (`uv run pytest && uv run ruff check .`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

GNU Affero General Public License - see LICENSE file for details.
