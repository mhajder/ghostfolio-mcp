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
