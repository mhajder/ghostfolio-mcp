import sys
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from ghostfolio_mcp import sentry_init


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_dsn_leaves_sentry_off(monkeypatch, value):
    monkeypatch.setenv("SENTRY_DSN", value)
    assert sentry_init.init_sentry() is False


@pytest.fixture
def fake_sentry(monkeypatch):
    """A stand-in sentry_sdk, so the test records init() without sending anything."""
    sdk = MagicMock()
    monkeypatch.setenv("SENTRY_DSN", "https://key@example.invalid/1")
    monkeypatch.delenv("SENTRY_SEND_DEFAULT_PII", raising=False)
    with patch.dict(
        sys.modules,
        {
            "sentry_sdk": sdk,
            "sentry_sdk.integrations": MagicMock(),
            "sentry_sdk.integrations.mcp": MagicMock(),
        },
    ):
        yield sdk.init


def test_sentry_sends_no_pii_unless_asked(fake_sentry):
    """Setting only SENTRY_DSN shipped tool arguments and results - holdings,
    orders, balances - to a third party without anyone opting in."""
    assert sentry_init.init_sentry() is True
    assert fake_sentry.call_args.kwargs["send_default_pii"] is False


def test_sentry_pii_can_still_be_opted_into(fake_sentry, monkeypatch):
    monkeypatch.setenv("SENTRY_SEND_DEFAULT_PII", "true")
    sentry_init.init_sentry()
    assert fake_sentry.call_args.kwargs["send_default_pii"] is True


def test_missing_sentry_sdk_warns_and_stays_off(monkeypatch, caplog):
    monkeypatch.setenv("SENTRY_DSN", "https://key@example.invalid/1")
    # A None entry makes the import raise ImportError.
    with patch.dict(sys.modules, {"sentry_sdk": None}):
        assert sentry_init.init_sentry() is False
    assert "Sentry SDK not installed" in caplog.text


def test_explicit_release_is_used(fake_sentry, monkeypatch):
    monkeypatch.setenv("SENTRY_RELEASE", "1.2.3")
    sentry_init.init_sentry()
    assert fake_sentry.call_args.kwargs["release"] == "1.2.3"


def test_release_defaults_to_the_installed_version(fake_sentry, monkeypatch):
    import importlib.metadata

    monkeypatch.delenv("SENTRY_RELEASE", raising=False)
    sentry_init.init_sentry()
    assert fake_sentry.call_args.kwargs["release"] == importlib.metadata.version(
        "ghostfolio-mcp"
    )


def test_release_is_none_when_the_package_is_not_installed(fake_sentry, monkeypatch):
    import importlib.metadata

    def missing(_name):
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.delenv("SENTRY_RELEASE", raising=False)
    monkeypatch.setattr(importlib.metadata, "version", missing)
    sentry_init.init_sentry()
    assert fake_sentry.call_args.kwargs["release"] is None


def test_init_failure_is_logged_not_raised(fake_sentry, caplog):
    fake_sentry.side_effect = RuntimeError("bad dsn")
    assert sentry_init.init_sentry() is False
    assert "Failed to initialize Sentry: bad dsn" in caplog.text
