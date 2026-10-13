import pytest

from ghostfolio_mcp.ghostfolio_client import get_ghostfolio_config_from_env

CONFIG_ENV_VARS = (
    "GHOSTFOLIO_URL",
    "GHOSTFOLIO_TOKEN",
    "GHOSTFOLIO_VERIFY_SSL",
    "GHOSTFOLIO_TIMEOUT",
    "GHOSTFOLIO_DISABLED_TAGS",
    "READ_ONLY_MODE",
    "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_MAX_REQUESTS",
    "RATE_LIMIT_WINDOW_MINUTES",
    "TOOL_SEARCH_ENABLED",
    "TOOL_SEARCH_STRATEGY",
    "TOOL_SEARCH_MAX_RESULTS",
)


# Isolates each test from the ambient environment.
@pytest.fixture(autouse=True)
def _clean_config_env(monkeypatch):
    for name in CONFIG_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GHOSTFOLIO_URL", "https://ghostfolio.invalid")
    monkeypatch.setenv("GHOSTFOLIO_TOKEN", "t")


@pytest.mark.parametrize(
    "name",
    [
        "READ_ONLY_MODE",
        "GHOSTFOLIO_VERIFY_SSL",
        "RATE_LIMIT_ENABLED",
        "TOOL_SEARCH_ENABLED",
    ],
)
def test_unknown_bool_setting_stops_startup(monkeypatch, name):
    """A typo must not turn read-only mode or TLS verification off."""
    monkeypatch.setenv(name, "enabled")
    with pytest.raises(ValueError, match=f"{name} must be one of"):
        get_ghostfolio_config_from_env()


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_timeout_uses_the_default(monkeypatch, value):
    monkeypatch.setenv("GHOSTFOLIO_TIMEOUT", value)
    assert get_ghostfolio_config_from_env().timeout == 30


def test_non_integer_timeout_names_the_variable(monkeypatch):
    monkeypatch.setenv("GHOSTFOLIO_TIMEOUT", "30s")
    with pytest.raises(ValueError, match="GHOSTFOLIO_TIMEOUT must be an integer"):
        get_ghostfolio_config_from_env()


def test_url_and_token_are_stripped_and_blank_counts_as_missing(monkeypatch):
    monkeypatch.setenv("GHOSTFOLIO_URL", "  https://ghostfolio.invalid  ")
    monkeypatch.setenv("GHOSTFOLIO_TOKEN", "   ")
    config = get_ghostfolio_config_from_env()
    assert config.ghostfolio_url == "https://ghostfolio.invalid"
    # Empty, so main() reports the token as missing instead of sending spaces.
    assert config.token == ""


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("RATE_LIMIT_MAX_REQUESTS", "0"),
        ("RATE_LIMIT_MAX_REQUESTS", "lots"),
        ("RATE_LIMIT_WINDOW_MINUTES", "-1"),
        ("TOOL_SEARCH_MAX_RESULTS", "0"),
        ("TOOL_SEARCH_MAX_RESULTS", "five"),
        ("TOOL_SEARCH_STRATEGY", "regx"),
    ],
)
def test_disabled_feature_ignores_its_settings(monkeypatch, name, value):
    """A leftover value for a feature that is off must not stop the server."""
    monkeypatch.setenv(name, value)
    config = get_ghostfolio_config_from_env()
    assert config.rate_limit_enabled is False
    assert config.tool_search_enabled is False


@pytest.mark.parametrize(
    ("switch", "name"),
    [
        ("RATE_LIMIT_ENABLED", "RATE_LIMIT_MAX_REQUESTS"),
        ("RATE_LIMIT_ENABLED", "RATE_LIMIT_WINDOW_MINUTES"),
        ("TOOL_SEARCH_ENABLED", "TOOL_SEARCH_MAX_RESULTS"),
    ],
)
def test_enabled_feature_rejects_zero(monkeypatch, switch, name):
    monkeypatch.setenv(switch, "true")
    monkeypatch.setenv(name, "0")
    with pytest.raises(ValueError, match=f"must be at least 1: {name}=0"):
        get_ghostfolio_config_from_env()


def test_enabled_feature_names_a_non_integer_setting(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "lots")
    with pytest.raises(ValueError, match="RATE_LIMIT_MAX_REQUESTS must be an integer"):
        get_ghostfolio_config_from_env()


def test_enabled_features_read_their_settings(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "10")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_MINUTES", "2")
    monkeypatch.setenv("TOOL_SEARCH_ENABLED", "true")
    monkeypatch.setenv("TOOL_SEARCH_STRATEGY", " Regex ")
    monkeypatch.setenv("TOOL_SEARCH_MAX_RESULTS", "8")
    config = get_ghostfolio_config_from_env()
    assert config.rate_limit_max_requests == 10
    assert config.rate_limit_window_minutes == 2
    assert config.tool_search_strategy == "regex"
    assert config.tool_search_max_results == 8


def test_unknown_tool_search_strategy_stops_startup_when_enabled(monkeypatch):
    monkeypatch.setenv("TOOL_SEARCH_ENABLED", "true")
    monkeypatch.setenv("TOOL_SEARCH_STRATEGY", "regx")
    with pytest.raises(ValueError, match="TOOL_SEARCH_STRATEGY must be 'bm25' or"):
        get_ghostfolio_config_from_env()


@pytest.mark.parametrize("value", ["0", "-5"])
def test_timeout_must_be_positive(monkeypatch, value):
    monkeypatch.setenv("GHOSTFOLIO_TIMEOUT", value)
    with pytest.raises(ValueError, match="timeout"):
        get_ghostfolio_config_from_env()
