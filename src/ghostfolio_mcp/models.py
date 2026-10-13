from typing import Literal

from pydantic import BaseModel
from pydantic import Field
from pydantic import model_validator


class GhostfolioConfig(BaseModel):
    ghostfolio_url: str = Field(
        ..., description="Ghostfolio base URL, e.g. https://domain.tld:3333"
    )
    token: str = Field(..., description="Ghostfolio API token")
    verify_ssl: bool = Field(True, description="Verify SSL (true/false)")
    timeout: int = Field(30, gt=0, description="Timeout in seconds")
    read_only_mode: bool = Field(False, description="Read-only mode (true/false)")
    disabled_tags: set[str] = Field(
        default_factory=set, description="Set of tags to disable tools for"
    )
    rate_limit_enabled: bool = Field(
        False, description="Enable rate limiting (true/false)"
    )
    rate_limit_max_requests: int = Field(60, description="Maximum requests per minute")
    rate_limit_window_minutes: int = Field(
        1, description="Rate limit window in minutes"
    )
    tool_search_enabled: bool = Field(
        False, description="Enable FastMCP tool search transform"
    )
    tool_search_strategy: Literal["bm25", "regex"] = Field(
        "bm25", description="Tool search strategy: 'bm25' (natural language) or 'regex'"
    )
    tool_search_max_results: int = Field(
        5,
        description="Maximum number of tools returned by search_tools",
    )

    @model_validator(mode="after")
    def _check_enabled_features(self) -> "GhostfolioConfig":
        """Validate the settings of enabled features only.

        A disabled feature's leftover values (RATE_LIMIT_MAX_REQUESTS=0 as a
        way to say "off", for instance) must not stop the server, but once the
        feature is on, a zero or negative value would reject every call (rate
        limiting) or return no tools (tool search) without explanation.
        """
        positive = {}
        if self.rate_limit_enabled:
            positive["RATE_LIMIT_MAX_REQUESTS"] = self.rate_limit_max_requests
            positive["RATE_LIMIT_WINDOW_MINUTES"] = self.rate_limit_window_minutes
        if self.tool_search_enabled:
            positive["TOOL_SEARCH_MAX_RESULTS"] = self.tool_search_max_results
        bad = [f"{name}={value}" for name, value in positive.items() if value < 1]
        if bad:
            raise ValueError(f"must be at least 1: {', '.join(bad)}")
        return self


class TransportConfig(BaseModel):
    """Configuration for MCP transport layer"""

    transport_type: str = Field(
        "stdio",
        description="Transport type: 'stdio', 'sse' (Server-Sent Events), or 'http' (HTTP Streamable)",
    )
    # HTTP transport settings (for both SSE and HTTP Streamable)
    http_host: str = Field(
        "127.0.0.1",
        description="Host to bind for HTTP transports (SSE/HTTP Streamable)",
    )
    http_port: int = Field(
        8000, description="Port to bind for HTTP transports (SSE/HTTP Streamable)"
    )
    http_bearer_token: str | None = Field(
        None, description="Bearer token for HTTP authentication"
    )
    # OIDC / OAuth. When config_url, client_id, client_secret and base_url are all
    # set, the server exposes an OAuth interface with Dynamic Client Registration
    # (FastMCP's OIDCProxy) brokered to an upstream identity provider, so MCP clients
    # that can only authenticate over OAuth are able to connect.
    oidc_config_url: str | None = Field(
        None,
        description="Upstream OIDC discovery URL (.../.well-known/openid-configuration)",
    )
    oidc_client_id: str | None = Field(
        None, description="Client ID registered with the upstream identity provider"
    )
    oidc_client_secret: str | None = Field(
        None, description="Client secret registered with the upstream identity provider"
    )
    oidc_base_url: str | None = Field(
        None,
        description="Public base URL where this server's OAuth endpoints are reachable",
    )
    oidc_redirect_path: str = Field(
        "/auth/callback",
        description="Callback path registered on the upstream identity provider",
    )
    oidc_required_scopes: list[str] | None = Field(
        None, description="Scopes required on presented tokens (None = do not enforce)"
    )
    oidc_allowed_redirect_uris: list[str] | None = Field(
        None,
        description=(
            "Allowed MCP client redirect URI patterns (wildcards accepted). "
            "None = OIDCProxy default (registered URIs plus loopback variance)"
        ),
    )
    oidc_verify_id_token: bool = Field(
        False,
        description=(
            "Verify the id_token instead of the access_token, for identity providers "
            "that issue opaque (non-JWT) access tokens"
        ),
    )
    oidc_forward_resource: bool = Field(
        False,
        description=(
            "Forward the RFC 8707 'resource' indicator to the upstream identity "
            "provider. Off by default because providers that do not implement "
            "resource indicators reject the authorization request with "
            "invalid_request. Token audience binding is unaffected."
        ),
    )

    def missing_oidc_settings(self) -> list[str]:
        """Names of OIDC settings that are needed but absent.

        Empty when OIDC is fully configured and when it is not configured at all;
        non-empty only for a half-configured setup, which is worth a warning
        because the server then falls back to whatever else is configured.
        """
        provided = {
            "OIDC_CONFIG_URL": self.oidc_config_url,
            "OIDC_CLIENT_ID": self.oidc_client_id,
            "OIDC_CLIENT_SECRET": self.oidc_client_secret,
            "OIDC_BASE_URL": self.oidc_base_url,
        }
        missing = [name for name, value in provided.items() if not value]
        return [] if len(missing) == len(provided) else missing

    def oidc_credentials(self) -> tuple[str, str, str, str] | None:
        """Return the four required OIDC settings, or None when OIDC is off."""
        if not (
            self.oidc_config_url
            and self.oidc_client_id
            and self.oidc_client_secret
            and self.oidc_base_url
        ):
            return None
        return (
            self.oidc_config_url,
            self.oidc_client_id,
            self.oidc_client_secret,
            self.oidc_base_url,
        )

    @property
    def oidc_enabled(self) -> bool:
        """OIDC is active only when every upstream credential is present."""
        return self.oidc_credentials() is not None
