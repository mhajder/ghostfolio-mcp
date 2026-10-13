import pytest

from ghostfolio_mcp.utils import env_bool
from ghostfolio_mcp.utils import env_float
from ghostfolio_mcp.utils import env_int
from ghostfolio_mcp.utils import env_str
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
        ("off", True, False),
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


@pytest.mark.parametrize("val", ["random", "enabled", "enable", "y", "2", "yep"])
@pytest.mark.parametrize("default", [True, False])
def test_parse_bool_rejects_unknown_values(val, default):
    """A typo must not read as False: READ_ONLY_MODE=enable would expose writes."""
    with pytest.raises(ValueError, match=f"got {val!r}"):
        parse_bool(val, default)


def test_env_bool_names_the_variable(monkeypatch):
    monkeypatch.setenv("READ_ONLY_MODE", "enable")
    with pytest.raises(ValueError, match="READ_ONLY_MODE must be one of true/false"):
        env_bool("READ_ONLY_MODE", default=False)


@pytest.mark.parametrize(("raw", "expected"), [(None, True), ("", True), ("no", False)])
def test_env_bool_reads_the_variable(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("GHOSTFOLIO_VERIFY_SSL", raising=False)
    else:
        monkeypatch.setenv("GHOSTFOLIO_VERIFY_SSL", raw)
    assert env_bool("GHOSTFOLIO_VERIFY_SSL", default=True) is expected


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
        # Blank counts as unset: loopback, not every interface.
        ("", "127.0.0.1"),
        ("  ", "127.0.0.1"),
        (" 0.0.0.0 ", "0.0.0.0"),  # noqa: S104
    ],
)
def test_http_host_from_env(monkeypatch, raw, expected):
    """The server and the healthcheck share this; uvicorn needs bare IPv6."""
    if raw is None:
        monkeypatch.delenv("MCP_HTTP_HOST", raising=False)
    else:
        monkeypatch.setenv("MCP_HTTP_HOST", raw)
    assert http_host_from_env() == expected


@pytest.mark.parametrize(
    ("raw", "expected"), [(None, 8000), ("9000", 9000), ("", 8000), (" 9000 ", 9000)]
)
def test_http_port_from_env(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("MCP_HTTP_PORT", raising=False)
    else:
        monkeypatch.setenv("MCP_HTTP_PORT", raw)
    assert http_port_from_env() == expected


def test_http_port_from_env_rejects_non_integer(monkeypatch):
    monkeypatch.setenv("MCP_HTTP_PORT", "abc")
    with pytest.raises(ValueError, match="MCP_HTTP_PORT must be an integer, got 'abc'"):
        http_port_from_env()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, None), ("", None), ("   ", None), (" secret ", "secret")],
)
def test_env_str_strips_and_treats_blank_as_unset(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("GHOSTFOLIO_TEST_STR", raising=False)
    else:
        monkeypatch.setenv("GHOSTFOLIO_TEST_STR", raw)
    assert env_str("GHOSTFOLIO_TEST_STR") == expected
    assert env_str("GHOSTFOLIO_TEST_STR", "fallback") == (expected or "fallback")


@pytest.mark.parametrize(
    ("raw", "expected"), [(None, 30), ("", 30), ("  ", 30), ("45", 45), (" 45 ", 45)]
)
def test_env_int_treats_blank_as_unset(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("GHOSTFOLIO_TEST_INT", raising=False)
    else:
        monkeypatch.setenv("GHOSTFOLIO_TEST_INT", raw)
    assert env_int("GHOSTFOLIO_TEST_INT", 30) == expected


def test_env_int_names_the_variable(monkeypatch):
    monkeypatch.setenv("GHOSTFOLIO_TEST_INT", "3O")
    with pytest.raises(ValueError, match="GHOSTFOLIO_TEST_INT must be an integer"):
        env_int("GHOSTFOLIO_TEST_INT", 30)


@pytest.mark.parametrize(("raw", "expected"), [(None, 1.0), ("", 1.0), ("0.25", 0.25)])
def test_env_float_treats_blank_as_unset(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("GHOSTFOLIO_TEST_FLOAT", raising=False)
    else:
        monkeypatch.setenv("GHOSTFOLIO_TEST_FLOAT", raw)
    assert env_float("GHOSTFOLIO_TEST_FLOAT", 1.0) == expected


def test_env_float_names_the_variable(monkeypatch):
    monkeypatch.setenv("GHOSTFOLIO_TEST_FLOAT", "half")
    with pytest.raises(ValueError, match="GHOSTFOLIO_TEST_FLOAT must be a number"):
        env_float("GHOSTFOLIO_TEST_FLOAT", 1.0)
