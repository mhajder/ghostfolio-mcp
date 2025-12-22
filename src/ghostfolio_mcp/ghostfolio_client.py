import logging
import os
from datetime import datetime
from datetime import timedelta
from typing import Any

import httpx

from ghostfolio_mcp.models import GhostfolioConfig
from ghostfolio_mcp.models import TransportConfig
from ghostfolio_mcp.utils import parse_bool

logger = logging.getLogger(__name__)


class GhostfolioClient:
    """Async client for Ghostfolio API using API token authentication"""

    _instance = None
    _initialized = False

    def __new__(cls, config: GhostfolioConfig | None = None):
        """Create a new instance of GhostfolioClient."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: GhostfolioConfig | None = None):
        """Initialize the GhostfolioClient."""
        if self._initialized:
            return
        if config is None:
            raise ValueError("Config must be provided for first initialization")
        self.config = config
        # Ensure trailing slash for base_url
        base = config.ghostfolio_url.rstrip("/")
        self.base_url = f"{base}/api"
        self.client: httpx.AsyncClient | None = None
        self._jwt_token: str | None = None
        self._jwt_token_expiry: datetime | None = None
        self._initialized = True

    async def __aenter__(self):
        """Enter the async context manager."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                verify=self.config.verify_ssl,
                timeout=self.config.timeout,
                base_url=self.base_url,
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager."""
        # Keep client for reuse
        pass

    async def close(self):
        """Close the HTTP client session."""
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    async def _refresh_jwt_token(self) -> None:
        """Refresh JWT token if expired or not present."""
        if (
            self._jwt_token is not None
            and self._jwt_token_expiry
            and self._jwt_token_expiry > datetime.now()
        ):
            return

        if self.client is None:
            raise RuntimeError("Client not initialized")

        resp = await self.client.post(
            "/v1/auth/anonymous/", json={"accessToken": self.config.token}
        )
        resp.raise_for_status()
        result = resp.json()
        self._jwt_token = result["authToken"]
        self._jwt_token_expiry = datetime.now() + timedelta(days=30)

    async def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        api_version: str = "v1",
        object_id: str | None = None,
    ) -> dict[str, Any]:
        """Perform a request to a Ghostfolio API path."""
        if self.client is None:
            raise RuntimeError(
                "Client not initialized - use 'async with GhostfolioClient(config)' or call __aenter__"
            )

        await self._refresh_jwt_token()

        # Build URL path
        url_path = f"/{api_version}/{path.lstrip('/')}"
        if object_id:
            url_path = f"{url_path.rstrip('/')}/{object_id}"
        if not url_path.endswith("/"):
            url_path += "/"

        headers = {"Authorization": f"Bearer {self._jwt_token}"}
        resp = await self.client.request(
            method, url_path, params=params, json=data, headers=headers
        )
        resp.raise_for_status()
        return resp.json()

    async def get(
        self, path: str, params: dict[str, Any] | None = None, api_version: str = "v1"
    ) -> dict[str, Any]:
        """Perform a GET request to a Ghostfolio API path."""
        return await self.request("GET", path, params=params, api_version=api_version)

    async def post(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        api_version: str = "v1",
        object_id: str | None = None,
    ) -> dict[str, Any]:
        """Perform a POST request to a Ghostfolio API path."""
        return await self.request(
            "POST", path, data=data, api_version=api_version, object_id=object_id
        )

    async def put(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        api_version: str = "v1",
        object_id: str | None = None,
    ) -> dict[str, Any]:
        """Perform a PUT request to a Ghostfolio API path."""
        return await self.request(
            "PUT", path, data=data, api_version=api_version, object_id=object_id
        )

    async def delete(
        self, path: str, params: dict[str, Any] | None = None, api_version: str = "v1"
    ) -> dict[str, Any]:
        """Perform a DELETE request to a Ghostfolio API path."""
        return await self.request(
            "DELETE", path, params=params, api_version=api_version
        )


def get_ghostfolio_config_from_env() -> GhostfolioConfig:
    """Get Ghostfolio configuration from environment variables."""
    # Parse disabled tags from comma-separated string
    disabled_tags_str = os.getenv("GHOSTFOLIO_DISABLED_TAGS", "")
    disabled_tags = set()
    if disabled_tags_str.strip():
        # Split by comma and strip whitespace from each tag
        disabled_tags = {
            tag.strip() for tag in disabled_tags_str.split(",") if tag.strip()
        }

    return GhostfolioConfig(
        ghostfolio_url=os.getenv("GHOSTFOLIO_URL"),
        token=os.getenv("GHOSTFOLIO_TOKEN"),
        verify_ssl=parse_bool(os.getenv("GHOSTFOLIO_VERIFY_SSL"), default=True),
        timeout=int(os.getenv("GHOSTFOLIO_TIMEOUT", "30")),
        read_only_mode=parse_bool(os.getenv("READ_ONLY_MODE"), default=False),
        disabled_tags=disabled_tags,
        rate_limit_enabled=parse_bool(os.getenv("RATE_LIMIT_ENABLED"), default=False),
        rate_limit_max_requests=int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "60")),
        rate_limit_window_minutes=int(os.getenv("RATE_LIMIT_WINDOW_MINUTES", "1")),
    )


def get_transport_config_from_env() -> TransportConfig:
    """Get transport configuration from environment variables."""
    return TransportConfig(
        transport_type=os.getenv("MCP_TRANSPORT", "stdio").lower(),
        http_host=os.getenv("MCP_HTTP_HOST", "0.0.0.0"),
        http_port=int(os.getenv("MCP_HTTP_PORT", "8000")),
        http_bearer_token=os.getenv("MCP_HTTP_BEARER_TOKEN"),
    )


_ghostfolio_client_singleton: GhostfolioClient | None = None


def get_ghostfolio_client(config: GhostfolioConfig | None = None) -> GhostfolioClient:
    """Get the singleton Ghostfolio client instance."""
    global _ghostfolio_client_singleton
    if _ghostfolio_client_singleton is None:
        if config is None:
            raise ValueError(
                "Ghostfolio config must be provided for first initialization"
            )
        _ghostfolio_client_singleton = GhostfolioClient(config)
    return _ghostfolio_client_singleton
