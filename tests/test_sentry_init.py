import pytest

from ghostfolio_mcp import sentry_init


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_dsn_leaves_sentry_off(monkeypatch, value):
    monkeypatch.setenv("SENTRY_DSN", value)
    assert sentry_init.init_sentry() is False
