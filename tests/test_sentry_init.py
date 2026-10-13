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
