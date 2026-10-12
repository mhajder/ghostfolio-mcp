"""
Container healthcheck: request the health endpoint when an HTTP transport is selected.

Run as ``python -m ghostfolio_mcp.healthcheck``. It loads the same .env file and
resolves MCP_TRANSPORT, MCP_HTTP_HOST and MCP_HTTP_PORT with the same helpers
as the server, so the two agree on what is configured. Only python-dotenv, the
standard library and ghostfolio_mcp.utils are imported, keeping each probe cheap.
"""

import http.client
import sys

from dotenv import load_dotenv

from ghostfolio_mcp.utils import HEALTH_PATH
from ghostfolio_mcp.utils import HTTP_TRANSPORTS
from ghostfolio_mcp.utils import http_host_from_env
from ghostfolio_mcp.utils import http_port_from_env
from ghostfolio_mcp.utils import transport_from_env

# Wildcard binds listen on every interface, loopback included. A blank host
# makes uvicorn listen on all interfaces, IPv4 and IPv6.
ALL_INTERFACES = ""
IPV4_WILDCARD = "0.0.0.0"  # noqa: S104
IPV6_WILDCARD = "::"

# The Dockerfile HEALTHCHECK timeout is 10s; two probes plus startup fit inside it.
PROBE_TIMEOUT_SECONDS = 2


def probe_hosts() -> list[str]:
    """Return the addresses to probe for MCP_HTTP_HOST, in order.

    A '::' bind is usually dual-stack, and containers often have no IPv6 on
    loopback, so it is probed on both ::1 and 127.0.0.1, as is a blank host.
    """
    host = http_host_from_env()
    if host == IPV4_WILDCARD:
        return ["127.0.0.1"]
    if host in (IPV6_WILDCARD, ALL_INTERFACES):
        return ["::1", "127.0.0.1"]
    return [host]


def probe(host: str, port: int) -> bool:
    """Return True when GET HEALTH_PATH on host:port answers 200.

    http.client is used directly rather than urllib, which would route the
    request through any HTTP(S)_PROXY set in the container's environment.
    """
    conn = http.client.HTTPConnection(host, port, timeout=PROBE_TIMEOUT_SECONDS)
    try:
        conn.request("GET", HEALTH_PATH)
        return conn.getresponse().status == 200
    except (OSError, http.client.HTTPException):
        return False
    finally:
        conn.close()


def main() -> int:
    """Return 0 when healthy, 1 when the health endpoint does not answer 200."""
    # The server loads .env before reading its settings; do the same so a
    # transport configured only there is probed too.
    load_dotenv()
    if transport_from_env() not in HTTP_TRANSPORTS:
        # Any other value runs the stdio transport, which has no port to probe.
        return 0
    port = http_port_from_env()
    return 0 if any(probe(host, port) for host in probe_hosts()) else 1


if __name__ == "__main__":
    sys.exit(main())
