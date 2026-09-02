## v1.6.2 (2026-09-02)

## v1.6.1 (2026-08-27)

### Fix

- **accounts**: fix account-balance writes (#71)

## v1.6.0 (2026-08-19)

### Feat

- **auth**: add optional OIDC/OAuth authentication for HTTP transports (#67)

### Fix

- **client**: percent-encode caller-supplied URL path segments
- **server**: resolve LOG_LEVEL case-insensitively
- **config**: treat blank env vars as unset

## v1.5.0 (2026-07-14)

### Feat

- **tools**: add watchlist, exchange-rates, export, benchmarks, and cash account tools

### Refactor

- **server**: improve server instructions in FastMCP initialization
- **tools**: split monolithic tools file into separate resource modules

## v1.4.3 (2026-07-06)

### Refactor

- update default HTTP bind address and improve transport validation

## v1.4.2 (2026-07-06)

### Fix

- **server**: configure FastMCP to disable banner and update checks
- **docker**: update base image from alpine3.23 to alpine3.24

## v1.4.1 (2026-06-05)

### Fix

- **tools**: get_orders hits renamed activities endpoint (#41)

## v1.4.0 (2026-05-11)

### Feat

- **tools**: add delete_asset_profile (#32)
- **tools**: add upsert_asset_profile (#31)
- **tools**: add add_market_data_points (#30)

### Fix

- **docker**: scope healthcheck to http transport mode (#33)

## v1.3.0 (2026-05-09)

### Feat

- **tools**: add account, activity, and system management endpoints

## v1.2.1 (2026-05-09)

### Fix

- handle trailing slash inconsistencies in Ghostfolio API
- **client**: trailing slash by HTTP method; tolerate empty response bodies (#29)
- declare import_transactions tags as a set, not a string (#27)

## v1.2.0 (2026-04-09)

### Feat

- add MCP Registry integration and metadata
- add optional tool search transform support

### Fix

- update healthcheck command to use nc for service availability
- **docker**: improve healthcheck configuration

### Refactor

- replace tag middleware with component visibility

## v1.1.0 (2025-12-22)

### Feat

- **docker**: update docker images, change default transport to http
- **sentry**: add optional Sentry integration for error tracking and performance monitoring
- **docker**: add Docker usage instructions for easy deployment
- add fastmcp.json configuration
- **sentry**: add optional Sentry integration for error tracking and performance monitoring
- add publish workflow to PyPI and update project metadata
- **deps**: add commitizen for conventional commits

### Fix

- update license classifier to AGPLv3+
- **server**: remove unnecessary dependencies from FastMCP initialization
- **workflows**: update actions/checkout and change MCPO docker image

## v1.0.0 (2025-08-29)
