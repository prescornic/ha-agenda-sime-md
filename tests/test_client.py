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


def test_invalidate_session():
    client = SimeClient("test_user", "test_pass", role=SimeAccountRole.PARENT)
    client.auth._authenticated = True
    client.auth.session_id = "12345"
    client.auth.portal_url = "https://agenda.sime.md/portal"
    client._student_urls["UK1"] = "https://agenda.sime.md/student1"

    client.invalidate_session()
    assert not client.auth.is_authenticated
    assert client.auth.session_id is None
    assert client.auth.portal_url is None
    assert len(client._student_urls) == 0
