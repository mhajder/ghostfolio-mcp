import pytest

from ghostfolio_mcp.utils import http_host_from_env
from ghostfolio_mcp.utils import http_port_from_env
from ghostfolio_mcp.utils import parse_bool
from ghostfolio_mcp.utils import quote_path_segment
from ghostfolio_mcp.utils import transport_from_env


@pytest.mark.parametrize(
    ("val", "default", "expected"),
    [
        (None, True, True),
        (None, False, False),
        ("1", False, True),
        ("true", False, True),
        ("yes", False, True),
        ("on", False, True),
        ("TrUe", False, True),
        ("YES", False, True),
        ("ON", False, True),
        ("1 ", False, True),
        ("0", True, False),
        ("false", True, False),
        ("no", True, False),
        ("random", True, False),
        ("False", True, False),
        # Blank means "unset", so the default wins rather than False.
        ("", True, True),
        ("", False, False),
        ("  ", True, True),
        ("  ", False, False),
    ],
)
def test_parse_bool(val, default, expected):
    assert parse_bool(val, default) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # Unreserved characters are left alone, so ordinary symbols, dates and
        # UUIDs produce exactly the same path as before encoding was added.
        ("AAPL", "AAPL"),
        ("BTC-USD", "BTC-USD"),
        ("TRUE-UNLISTED", "TRUE-UNLISTED"),
        ("2026-04-30", "2026-04-30"),
        (
            "cb547e5c-1234-5678-9abc-def012345678",
            "cb547e5c-1234-5678-9abc-def012345678",
        ),
        ("MANUAL", "MANUAL"),
        # Characters that would otherwise change where the request goes.
        ("A#B", "A%23B"),  # fragment: silently truncated the path
        ("BTC/USD", "BTC%2FUSD"),  # extra path segment
        ("A?B", "A%3FB"),  # start of the query string
        ("BRK B", "BRK%20B"),
        ("A%B", "A%25B"),
        # Dot-only segments survive quoting as-is ('.' is unreserved) and are
        # then removed by dot-segment normalisation, so escape the dots too.
        (".", "%2E"),
        ("..", "%2E%2E"),
        ("...", "%2E%2E%2E"),
        # Dots elsewhere in the value are harmless and stay readable.
        ("BRK.B", "BRK.B"),
    ],
)
def test_quote_path_segment(value, expected):
    assert quote_path_segment(value) == expected


@pytest.mark.parametrize("value", ["", " ", "\t", "\n  "])
def test_quote_path_segment_rejects_empty(value):
    # An empty segment collapses into the trailing slash and turns an item
    # request into a collection one, so there is no safe request to make.
    with pytest.raises(ValueError, match="must not be empty"):
        quote_path_segment(value)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, "stdio"),
        ("http", "http"),
        ("SSE", "sse"),
        # FastMCP's name for the streamable HTTP transport.
        ("streamable-http", "http"),
        # Only lowercased: anything else selects stdio in the server.
        (" http ", " http "),
        ("", ""),
    ],
)
def test_transport_from_env(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("MCP_TRANSPORT", raising=False)
    else:
        monkeypatch.setenv("MCP_TRANSPORT", raw)
    assert transport_from_env() == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, "127.0.0.1"),
        ("0.0.0.0", "0.0.0.0"),  # noqa: S104
        ("::", "::"),
        # The URL form of an IPv6 literal; uvicorn needs it bare.
        ("[::]", "::"),
        ("[fd00::5]", "fd00::5"),
        ("", ""),
    ],
)
def test_http_host_from_env(monkeypatch, raw, expected):
    """The server and the healthcheck share this; uvicorn needs bare IPv6."""
    if raw is None:
        monkeypatch.delenv("MCP_HTTP_HOST", raising=False)
    else:
        monkeypatch.setenv("MCP_HTTP_HOST", raw)
    assert http_host_from_env() == expected


@pytest.mark.parametrize(("raw", "expected"), [(None, 8000), ("9000", 9000)])
def test_http_port_from_env(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("MCP_HTTP_PORT", raising=False)
    else:
        monkeypatch.setenv("MCP_HTTP_PORT", raw)
    assert http_port_from_env() == expected


def test_http_port_from_env_rejects_non_integer(monkeypatch):
    monkeypatch.setenv("MCP_HTTP_PORT", "abc")
    with pytest.raises(ValueError, match="invalid literal for int"):
        http_port_from_env()
