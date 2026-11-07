# Changelog

## [1.8.2](https://github.com/mhajder/ghostfolio-mcp/compare/v1.8.1...v1.8.2) (2026-11-07)


### 🐛 Bug Fixes

* **accounts:** tag get_accounts with 'account' like the other account tools ([4f33544](https://github.com/mhajder/ghostfolio-mcp/commit/4f3354472fa7e70ffd60462229565ce1fa951b56))


### 🧩 CI

* pin actions to commit SHAs at latest versions ([cbaf98b](https://github.com/mhajder/ghostfolio-mcp/commit/cbaf98b33b8895e308f5d7d4245427b9400d9e63))
* release with release-please ([9918c9b](https://github.com/mhajder/ghostfolio-mcp/commit/9918c9b10ae0a409eb8ed1f7002cc05e53d8d4d4))
* replace softprops/action-gh-release with the gh CLI ([bd02fc1](https://github.com/mhajder/ghostfolio-mcp/commit/bd02fc1940240fcb3901b3f9474b75adabec68d0))


### 📦 Build

* **deps:** bump ty to 0.0.98 and type check for all platforms ([0aff346](https://github.com/mhajder/ghostfolio-mcp/commit/0aff34697fd99a209528e489df205db5098d108f))
* **deps:** raise minimum versions of dev tools and vulnerable dependencies ([1f270f6](https://github.com/mhajder/ghostfolio-mcp/commit/1f270f63cdebfaff156c1a7965db7f313867ebc6))
* **deps:** stop Dependabot proposing Python pre-release and minor bumps ([48202bb](https://github.com/mhajder/ghostfolio-mcp/commit/48202bb66df3ba507fa6f6e952ee7a8a9ed8effc))
* **docker:** pin base images by version and digest and update them with Dependabot ([688f72d](https://github.com/mhajder/ghostfolio-mcp/commit/688f72d6a819007095b20cc043820fd656fb871d))
* install optional extras for ty check in pre-commit hook ([47c25ae](https://github.com/mhajder/ghostfolio-mcp/commit/47c25ae31dbb61e886b2f61a1201ad30bb3f7565))


### 🧪 Tests

* raise line coverage to 100% ([dd5f49e](https://github.com/mhajder/ghostfolio-mcp/commit/dd5f49ed30c2b8fb845812a59ad547bf0b4864f7))

## v1.8.1 (2026-10-23)

### Fix

- **deps**: update certifi to 2026.10.19

## v1.8.0 (2026-10-19)

### Feat

- **activities**: add tags support to create_activity and new update_activity tool (#89)
- **transport**: accept streamable-http as an alias for http
- add Python 3.15 support
- **health**: serve /health and probe it from the Docker healthcheck
- **docker**: drop the MCPO image

### Fix

- **accounts**: stop update_account from sending nulls for name and currency
- **activities**: stop update_activity from writing wrong or missing values
- **transport**: stop on an unknown MCP_TRANSPORT instead of running stdio
- **sentry**: send no PII unless SENTRY_SEND_DEFAULT_PII asks for it
- **transport**: ignore surrounding spaces in MCP_TRANSPORT
- **transport**: bind loopback when MCP_HTTP_HOST is blank
- **config**: validate settings of enabled features only
- **config**: treat blank env values as unset
- **config**: reject unrecognized boolean settings
- **sentry**: log the enabled message by initialising after logging
- **docker**: run as numeric UID 10001 with root-owned app files

### Refactor

- **server**: read config attributes directly

## v1.7.0 (2026-09-17)

### Feat

- **assets**: support countries and sectors in upsert_asset_profile

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
