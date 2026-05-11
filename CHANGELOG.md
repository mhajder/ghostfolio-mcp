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
