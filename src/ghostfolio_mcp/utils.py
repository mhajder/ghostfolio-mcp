import os
from collections.abc import Callable
from typing import TypeVar
from urllib.parse import quote

TRUTHY_VALUES = ("true", "1", "yes", "on")
FALSY_VALUES = ("false", "0", "no", "off")
# "true/false, 1/0, yes/no, on/off", for error messages.
BOOL_HELP = ", ".join(
    f"{t}/{f}" for t, f in zip(TRUTHY_VALUES, FALSY_VALUES, strict=True)
)

# MCP_TRANSPORT values that serve HTTP. Anything else runs the stdio transport.
HTTP_TRANSPORTS = frozenset({"sse", "http"})
# FastMCP calls the streamable HTTP transport "streamable-http"; accept that
# spelling for the "http" transport this server documents.
TRANSPORT_ALIASES = {"streamable-http": "http"}

# Liveness endpoint served on the HTTP transports and probed by the container
# healthcheck.
HEALTH_PATH = "/health"


def transport_from_env() -> str:
    """
    Return MCP_TRANSPORT stripped and lowercased, defaulting to stdio when
    unset or blank.

    The server and the container healthcheck both read the transport here, so
    they always agree on it. Values outside HTTP_TRANSPORTS select stdio.

    'streamable-http' is read as 'http', FastMCP's name for that transport.
    """
    transport = (env_str("MCP_TRANSPORT") or "stdio").lower()
    return TRANSPORT_ALIASES.get(transport, transport)


def http_host_from_env() -> str:
    """
    Return MCP_HTTP_HOST stripped and without IPv6 brackets, defaulting to
    loopback when unset or blank.

    The server and the container healthcheck both read the bind address here,
    so they always agree on it. A blank value would make uvicorn listen on
    every interface; it binds loopback instead, so exposing the server always
    takes an explicit address such as 0.0.0.0.
    """
    host = env_str("MCP_HTTP_HOST") or "127.0.0.1"
    # Accept the URL form of an IPv6 literal ('[::]'); uvicorn needs it bare.
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    return host


def http_port_from_env() -> int:
    """
    Return MCP_HTTP_PORT as an integer, defaulting to 8000 when unset or blank.

    Raises:
        ValueError: If the variable is set to something that is not an integer.
    """
    return env_int("MCP_HTTP_PORT", 8000)


def env_str(name: str, default: str | None = None) -> str | None:
    """
    Read a string environment variable, stripped.

    A blank or whitespace-only value counts as unset and yields the default, so
    a declared-but-empty secret or URL is not mistaken for a real one.
    """
    value = (os.getenv(name) or "").strip()
    return value or default


_Number = TypeVar("_Number", int, float)


def _env_number(
    name: str, default: _Number, cast: Callable[[str], _Number], kind: str
) -> _Number:
    """Read a numeric environment variable, treating a blank value as unset."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return cast(raw.strip())
    except ValueError:
        raise ValueError(f"{name} must be {kind}, got {raw!r}") from None


def env_int(name: str, default: int) -> int:
    """
    Read an integer environment variable, treating a blank value as unset.

    Raises:
        ValueError: If the variable is set to something that is not an integer.
    """
    return _env_number(name, default, int, "an integer")


def env_float(name: str, default: float) -> float:
    """
    Read a float environment variable, treating a blank value as unset.

    Raises:
        ValueError: If the variable is set to something that is not a number.
    """
    return _env_number(name, default, float, "a number")


def parse_bool(val, default=True):
    """
    Convert a value to boolean.

    A blank or whitespace-only value counts as unset and yields the default,
    so an env var declared without a value (``GHOSTFOLIO_VERIFY_SSL=``) cannot
    silently flip a setting off. Any other value must be a recognized spelling:
    a typo such as ``READ_ONLY_MODE=enable`` raises instead of reading as False,
    which would expose the write tools or disable TLS verification.

    Args:
        val: The value to convert.
        default (bool, optional): The default value to return if val is None or blank. Defaults to True.

    Returns:
        bool: True for "true", "1", "yes", "on"; False for "false", "0", "no",
        "off" (case-insensitive).

    Raises:
        ValueError: If val is set to anything else.
    """
    if val is None:
        return default
    normalized = str(val).strip().casefold()
    if not normalized:
        return default
    if normalized in TRUTHY_VALUES:
        return True
    if normalized in FALSY_VALUES:
        return False
    raise ValueError(f"Expected a boolean ({BOOL_HELP}), got {val!r}")


def env_bool(name: str, default: bool) -> bool:
    """
    Read a boolean environment variable, treating a blank value as unset.

    Raises:
        ValueError: If the variable is set to an unrecognized value.
    """
    try:
        return parse_bool(os.getenv(name), default)
    except ValueError:
        raise ValueError(
            f"{name} must be one of {BOOL_HELP}, got {os.getenv(name)!r}"
        ) from None


def quote_path_segment(value: str) -> str:
    """
    Percent-encode a value for use as a single URL path segment.

    Ghostfolio path parameters are caller-supplied (symbols on a MANUAL data
    source are named by the user), so they can contain characters that carry
    meaning in a URL. Interpolating them raw silently sends the request
    somewhere else: ``#`` starts a fragment and truncates the path, ``?``
    starts the query string, and ``/`` adds a path segment. On a write or a
    delete that means acting on a *different* symbol - and getting a success
    response for it.

    Nothing is treated as safe, so ``/`` becomes ``%2F`` and stays inside the
    segment. Values made up of unreserved characters (the common case, e.g.
    ``AAPL``, ``2026-04-30`` or a UUID) come back unchanged, and httpx2 does not
    re-encode the escapes this produces.

    Two cases percent-encoding alone does not cover, because ``.`` is an
    unreserved character:

    - A dot-only segment (``.``, ``..``) is removed by RFC 3986 dot-segment
      normalisation, which walks the request up to a different endpoint. The
      dots are escaped so the value stays a value.
    - An empty segment collapses into the trailing slash, turning an
      item request into a collection one - ``delete_activity("")`` would issue
      ``DELETE /api/v1/activities``, which deletes *every* activity. There is
      no correct request to make for an empty identifier, so this raises.

    Args:
        value: The path segment value to encode.

    Returns:
        str: The percent-encoded segment.

    Raises:
        ValueError: If the value is empty or whitespace-only.
    """
    segment = str(value)
    if not segment.strip():
        raise ValueError(
            "URL path segment must not be empty - a symbol, date or ID is required"
        )
    encoded = quote(segment, safe="")
    if set(encoded) == {"."}:
        encoded = encoded.replace(".", "%2E")
    return encoded
