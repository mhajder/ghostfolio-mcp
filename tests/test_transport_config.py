import pytest

from ghostfolio_mcp.ghostfolio_client import get_transport_config_from_env
from ghostfolio_mcp.models import TransportConfig

OIDC_ENV = {
    "OIDC_CONFIG_URL": "https://id.example.com/.well-known/openid-configuration",
    "OIDC_CLIENT_ID": "client-id",
    "OIDC_CLIENT_SECRET": "client-secret",
    "OIDC_BASE_URL": "https://mcp.example.com",
}

TRANSPORT_ENV_VARS = (
    "MCP_TRANSPORT",
    "MCP_HTTP_HOST",
    "MCP_HTTP_PORT",
    "MCP_HTTP_BEARER_TOKEN",
    "OIDC_CONFIG_URL",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET",
    "OIDC_BASE_URL",
    "OIDC_REDIRECT_PATH",
    "OIDC_REQUIRED_SCOPES",
    "OIDC_ALLOWED_REDIRECT_URIS",
    "OIDC_VERIFY_ID_TOKEN",
    "OIDC_FORWARD_RESOURCE",
)


# Isolates each test from the ambient environment and any local .env file.
@pytest.fixture(autouse=True)
def _clean_transport_env(monkeypatch):
    for name in TRANSPORT_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_defaults_disable_oidc_and_leave_guard_unset():
    config = get_transport_config_from_env()

    assert config.oidc_enabled is False
    assert config.oidc_redirect_path == "/auth/callback"
    assert config.oidc_forward_resource is False
    assert config.oidc_verify_id_token is False


def test_full_oidc_environment_enables_oidc(monkeypatch):
    for name, value in OIDC_ENV.items():
        monkeypatch.setenv(name, value)

    config = get_transport_config_from_env()

    assert config.oidc_enabled is True
    assert config.oidc_config_url == OIDC_ENV["OIDC_CONFIG_URL"]
    assert config.oidc_base_url == "https://mcp.example.com"


# A half-configured setup must not block startup, only stay disabled.
def test_partial_oidc_environment_does_not_enable_oidc(monkeypatch):
    monkeypatch.setenv("OIDC_CONFIG_URL", OIDC_ENV["OIDC_CONFIG_URL"])
    monkeypatch.setenv("OIDC_CLIENT_ID", "client-id")

    config = get_transport_config_from_env()

    assert config.oidc_enabled is False
    assert config.missing_oidc_settings() == ["OIDC_CLIENT_SECRET", "OIDC_BASE_URL"]


def test_blank_oidc_values_count_as_unset(monkeypatch):
    for name in OIDC_ENV:
        monkeypatch.setenv(name, "   ")

    config = get_transport_config_from_env()

    assert config.oidc_enabled is False
    assert config.oidc_config_url is None


# A declared-but-empty value must not become an empty redirect path.
@pytest.mark.parametrize("value", ["", "   "])
def test_blank_redirect_path_falls_back_to_the_default(monkeypatch, value):
    monkeypatch.setenv("OIDC_REDIRECT_PATH", value)

    assert get_transport_config_from_env().oidc_redirect_path == "/auth/callback"


def test_redirect_path_is_read_and_stripped(monkeypatch):
    monkeypatch.setenv("OIDC_REDIRECT_PATH", "  /oauth/callback  ")

    assert get_transport_config_from_env().oidc_redirect_path == "/oauth/callback"


def test_comma_separated_values_are_split_and_stripped(monkeypatch):
    monkeypatch.setenv("OIDC_REQUIRED_SCOPES", " openid , profile ")
    monkeypatch.setenv("OIDC_ALLOWED_REDIRECT_URIS", "https://example.com/*")

    config = get_transport_config_from_env()

    assert config.oidc_required_scopes == ["openid", "profile"]
    assert config.oidc_allowed_redirect_uris == ["https://example.com/*"]


@pytest.mark.parametrize("value", ["", "  ", ",", " , "])
def test_blank_comma_separated_values_are_unset(monkeypatch, value):
    monkeypatch.setenv("OIDC_REQUIRED_SCOPES", value)

    assert get_transport_config_from_env().oidc_required_scopes is None


@pytest.mark.parametrize(
    "settings",
    [
        {},
        {
            "oidc_config_url": "https://id.example.com",
            "oidc_client_id": "client-id",
            "oidc_client_secret": "client-secret",
            "oidc_base_url": "https://mcp.example.com",
        },
    ],
)
def test_oidc_enabled_requires_every_setting(settings):
    assert TransportConfig(**settings).oidc_enabled is bool(settings)


@pytest.mark.parametrize(
    "omitted",
    ["oidc_config_url", "oidc_client_id", "oidc_client_secret", "oidc_base_url"],
)
def test_missing_oidc_settings_reports_each_absent_field(omitted):
    settings = {
        "oidc_config_url": "https://id.example.com",
        "oidc_client_id": "client-id",
        "oidc_client_secret": "client-secret",
        "oidc_base_url": "https://mcp.example.com",
    }
    del settings[omitted]

    config = TransportConfig(**settings)

    assert config.missing_oidc_settings() == [omitted.upper()]
    assert config.oidc_enabled is False


@pytest.mark.parametrize(
    "settings",
    [
        {},
        {
            "oidc_config_url": "https://id.example.com",
            "oidc_client_id": "client-id",
            "oidc_client_secret": "client-secret",
            "oidc_base_url": "https://mcp.example.com",
        },
    ],
)
# Nothing to report when OIDC is fully configured or not configured at all.
def test_missing_oidc_settings_is_empty_when_all_or_nothing_is_set(settings):
    assert TransportConfig(**settings).missing_oidc_settings() == []


@pytest.mark.parametrize("name", ["OIDC_VERIFY_ID_TOKEN", "OIDC_FORWARD_RESOURCE"])
def test_unknown_oidc_bool_setting_is_rejected(monkeypatch, name):
    monkeypatch.setenv(name, "yep")
    with pytest.raises(ValueError, match=f"{name} must be one of"):
        get_transport_config_from_env()


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_bearer_token_counts_as_unset(monkeypatch, value):
    """A whitespace-only token must not become the token clients have to send."""
    monkeypatch.setenv("MCP_HTTP_BEARER_TOKEN", value)
    assert get_transport_config_from_env().http_bearer_token is None


def test_bearer_token_is_stripped(monkeypatch):
    monkeypatch.setenv("MCP_HTTP_BEARER_TOKEN", "  s3cret  ")
    assert get_transport_config_from_env().http_bearer_token == "s3cret"  # noqa: S105
