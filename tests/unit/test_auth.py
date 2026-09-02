import logging
from datetime import UTC, datetime, timedelta

import pytest

from plato_mcp.auth import PlatoSession, SessionManager
from plato_mcp.errors import AuthError, UbboardLoginError


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


def _make_mock_http_session(mocker, has_cookie: bool, page_text: str):
    mock_http = mocker.MagicMock()
    login_page_resp = mocker.Mock()
    login_page_resp.text = (
        '<form id="form-login-sso"><input name="logintoken" value="TOK123" /></form>'
    )
    post_resp = mocker.Mock()
    post_resp.text = page_text
    mock_http.get.return_value = login_page_resp
    mock_http.post.return_value = post_resp
    mock_http.cookies = {"MoodleSession": "xyz"} if has_cookie else {}
    return mock_http


def test_cookie_login_success(manager, mocker):
    mock_http = _make_mock_http_session(
        mocker, has_cookie=True, page_text='logout.php link here "sesskey":"ABC123"'
    )
    mocker.patch("plato_mcp.auth.requests.Session", return_value=mock_http)

    http_session, sesskey = manager._cookie_login("202443155", "hunter2")
    assert http_session is mock_http
    assert sesskey == "ABC123"


def test_cookie_login_missing_cookie_raises_ubboard_login_error(manager, mocker):
    mock_http = _make_mock_http_session(mocker, has_cookie=False, page_text="invalid login")
    mocker.patch("plato_mcp.auth.requests.Session", return_value=mock_http)

    with pytest.raises(UbboardLoginError):
        manager._cookie_login("202443155", "wrong-password")


def test_cookie_login_missing_form_raises_ubboard_login_error(manager, mocker):
    mock_http = mocker.MagicMock()
    resp = mocker.Mock()
    resp.text = "<html>no login form here</html>"
    mock_http.get.return_value = resp
    mocker.patch("plato_mcp.auth.requests.Session", return_value=mock_http)

    with pytest.raises(UbboardLoginError):
        manager._cookie_login("u1", "p1")


def test_ubboard_login_error_is_an_auth_error_subclass():
    assert issubclass(UbboardLoginError, AuthError)


def test_cookie_login_failure_log_never_contains_password(manager, mocker, caplog):
    mock_http = _make_mock_http_session(mocker, has_cookie=False, page_text="invalid login")
    mocker.patch("plato_mcp.auth.requests.Session", return_value=mock_http)

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(UbboardLoginError):
            manager._cookie_login("202443155", "super-secret-password")

    for record in caplog.records:
        assert "super-secret-password" not in record.getMessage()


def test_ensure_ubboard_session_creates_new(manager, mocker):
    fake_http = mocker.Mock()
    mocker.patch.object(manager, "_cookie_login", return_value=(fake_http, "sess123"))

    session = manager.ensure_ubboard_session("session-1", "u1", "p1")
    assert session.requests_session is fake_http
    assert session.ubboard_sesskey == "sess123"


def test_ensure_ubboard_session_reuses_cached_session(manager, mocker):
    fake_http = mocker.Mock()
    cookie_login = mocker.patch.object(
        manager, "_cookie_login", return_value=(fake_http, "sess123")
    )

    manager.ensure_ubboard_session("session-1", "u1", "p1")
    manager.ensure_ubboard_session("session-1", "u1", "p1")
    assert cookie_login.call_count == 1


def test_get_or_login_then_ensure_ubboard_session_share_one_session_object(manager, mocker):
    mocker.patch.object(manager, "_fetch_token", return_value="tok-abc")
    fake_http = mocker.Mock()
    mocker.patch.object(manager, "_cookie_login", return_value=(fake_http, "sess123"))

    s1 = manager.get_or_login("session-1", "u1", "p1")
    s2 = manager.ensure_ubboard_session("session-1", "u1", "p1")

    assert s1 is s2
    assert s2.wstoken == "tok-abc"
    assert s2.ubboard_sesskey == "sess123"


def test_ensure_ubboard_session_then_get_or_login_preserves_cookie_session(manager, mocker):
    """Regression test: get_or_login used to blindly replace the cached
    PlatoSession, which would silently discard a cookie session attached
    by an earlier ensure_ubboard_session() call for the same session key."""
    fake_http = mocker.Mock()
    mocker.patch.object(manager, "_cookie_login", return_value=(fake_http, "sess123"))
    mocker.patch.object(manager, "_fetch_token", return_value="tok-abc")

    s1 = manager.ensure_ubboard_session("session-1", "u1", "p1")
    s2 = manager.get_or_login("session-1", "u1", "p1")

    assert s1 is s2
    assert s2.wstoken == "tok-abc"
    assert s2.requests_session is fake_http
    assert s2.ubboard_sesskey == "sess123"
