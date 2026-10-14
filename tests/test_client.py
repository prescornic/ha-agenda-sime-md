"""Unit tests for SimeClient."""

from lib.agenda_sime_md import (
    SimeAccountRole,
    SimeAuthError,
    SimeClient,
    SimeRateLimitError,
)


def test_client_init():
    client = SimeClient("test_user", "test_pass", role=SimeAccountRole.PARENT)
    assert client.username == "test_user"
    assert client.password == "test_pass"
    assert client.role == SimeAccountRole.PARENT
    assert not client.auth.is_authenticated


def test_rate_limit_error():
    err = SimeRateLimitError("Blocked", wait_seconds=45)
    assert isinstance(err, SimeAuthError)
    assert err.wait_seconds == 45
