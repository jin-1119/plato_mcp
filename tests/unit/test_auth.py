import logging
from datetime import UTC, datetime, timedelta

import pytest

from plato_mcp.auth import PlatoSession, SessionManager
from plato_mcp.errors import AuthError


@pytest.fixture
def manager():
    return SessionManager(idle_ttl=timedelta(minutes=30))


def test_cache_miss_then_hit(manager, mocker):
    fetch = mocker.patch.object(manager, "_fetch_token", return_value="tok-abc123")

    s1 = manager.get_or_login("session-1", "202443155", "hunter2")
    assert s1.wstoken == "tok-abc123"
    assert fetch.call_count == 1

    s2 = manager.get_or_login("session-1", "202443155", "hunter2")
    assert s2 is s1
    assert fetch.call_count == 1  # cache hit, no second login


def test_different_session_keys_dont_share_cache(manager, mocker):
    fetch = mocker.patch.object(manager, "_fetch_token", return_value="tok-abc123")

    manager.get_or_login("session-1", "u1", "p1")
    manager.get_or_login("session-2", "u2", "p2")
    assert fetch.call_count == 2


def test_ttl_eviction_forces_relogin(mocker):
    manager = SessionManager(idle_ttl=timedelta(milliseconds=1))
    fetch = mocker.patch.object(manager, "_fetch_token", return_value="tok-abc123")

    manager.get_or_login("session-1", "u1", "p1")
    assert fetch.call_count == 1

    # Simulate time passing beyond the TTL.
    stale_session = manager._cache["session-1"]
    stale_session.last_used_at = datetime.now(UTC) - timedelta(minutes=1)

    manager.get_or_login("session-1", "u1", "p1")
    assert fetch.call_count == 2  # evicted, so this was a fresh login


def test_require_session_raises_without_login(manager):
    with pytest.raises(AuthError):
        manager.require_session("never-logged-in")


def test_require_session_succeeds_after_login(manager, mocker):
    mocker.patch.object(manager, "_fetch_token", return_value="tok-abc123")
    manager.get_or_login("session-1", "u1", "p1")
    session = manager.require_session("session-1")
    assert session.wstoken == "tok-abc123"


def test_refresh_forces_new_login(manager, mocker):
    fetch = mocker.patch.object(manager, "_fetch_token", side_effect=["tok-old", "tok-new"])

    manager.get_or_login("session-1", "u1", "p1")
    assert manager.require_session("session-1").wstoken == "tok-old"

    manager.refresh("session-1", "u1", "p1")
    assert fetch.call_count == 2
    assert manager.require_session("session-1").wstoken == "tok-new"


def test_login_failure_raises_auth_error_without_leaking_password(manager, mocker):
    mocker.patch.object(
        manager, "_fetch_token",
        side_effect=AuthError("PLATO login failed (invalidlogin)"),
    )
    with pytest.raises(AuthError) as excinfo:
        manager.get_or_login("session-1", "202443155", "super-secret-password")
    assert "super-secret-password" not in str(excinfo.value)


def test_fetch_token_failure_log_never_contains_password(manager, mocker, caplog):
    """Exercise the real _fetch_token error path (mocked HTTP) and assert no
    log record at any level contains the raw password."""
    mock_response = mocker.Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"errorcode": "invalidlogin", "error": "bad login"}
    mocker.patch("plato_mcp.auth.requests.get", return_value=mock_response)

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(AuthError):
            manager._fetch_token("202443155", "super-secret-password")

    for record in caplog.records:
        assert "super-secret-password" not in record.getMessage()


def test_plato_session_repr_never_contains_wstoken_or_raw_username():
    session = PlatoSession(username="202443155", wstoken="tok-verysecrettoken")
    r = repr(session)
    assert "tok-verysecrettoken" not in r
    assert "202443155" not in r  # only the redacted "20***" form should appear
    assert "<set>" in r


def test_invalidate_removes_session(manager, mocker):
    mocker.patch.object(manager, "_fetch_token", return_value="tok-abc123")
    manager.get_or_login("session-1", "u1", "p1")
    manager.invalidate("session-1")
    with pytest.raises(AuthError):
        manager.require_session("session-1")
