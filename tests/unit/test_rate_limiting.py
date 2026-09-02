"""Issue #35: rate limiting for outbound PLATO requests, and a cap on
consecutive failed login attempts per session."""

import pytest

from plato_mcp.auth import MAX_LOGIN_ATTEMPTS, SessionManager
from plato_mcp.errors import AuthError, RateLimitError
from plato_mcp.moodle_client import MoodleClient
from plato_mcp.security import RateLimiter, TokenBucket, default_rate_limiter

# ---------------------------------------------------------------------------
# TokenBucket / RateLimiter unit behavior (isolated instances, not the global)
# ---------------------------------------------------------------------------


def test_token_bucket_allows_up_to_capacity_then_blocks():
    bucket = TokenBucket(capacity=3, refill_per_second=0)  # no refill during the test
    assert bucket.try_consume() is True
    assert bucket.try_consume() is True
    assert bucket.try_consume() is True
    assert bucket.try_consume() is False  # exhausted


def test_token_bucket_refills_over_time(mocker):
    bucket = TokenBucket(capacity=1, refill_per_second=10)
    assert bucket.try_consume() is True
    assert bucket.try_consume() is False  # empty

    # Simulate 0.2s passing (10 tokens/sec * 0.2s = 2 tokens, capped at capacity=1).
    mocker.patch("time.monotonic", return_value=bucket._last_refill + 0.2)
    assert bucket.try_consume() is True


def test_rate_limiter_global_budget_blocks_before_per_session_budget():
    limiter = RateLimiter(
        global_capacity=1,
        global_refill_per_second=0,
        per_session_capacity=100,
        per_session_refill_per_second=0,
    )
    limiter.check("session-a")  # consumes the one global token
    with pytest.raises(RateLimitError, match="server"):
        limiter.check("session-b")  # different session, but global budget is gone


def test_rate_limiter_per_session_budget_is_independent_per_key():
    limiter = RateLimiter(
        global_capacity=100,
        global_refill_per_second=0,
        per_session_capacity=1,
        per_session_refill_per_second=0,
    )
    limiter.check("session-a")  # exhausts session-a's own budget
    with pytest.raises(RateLimitError, match="session"):
        limiter.check("session-a")
    limiter.check("session-b")  # unaffected -- different session key


def test_rate_limiter_reconfigure_replaces_buckets_in_place():
    limiter = RateLimiter(global_capacity=1, global_refill_per_second=0)
    limiter.check("k")
    with pytest.raises(RateLimitError):
        limiter.check("k")

    limiter.reconfigure(global_capacity=100, global_refill_per_second=100)
    limiter.check("k")  # no longer exhausted


# ---------------------------------------------------------------------------
# Wired into moodle_client.py (uses the real default_rate_limiter, reconfigured)
# ---------------------------------------------------------------------------


def test_moodle_client_call_raises_rate_limit_error_when_exhausted(mocker):
    manager = SessionManager()
    mocker.patch.object(manager, "_fetch_token", return_value="tok")
    # Login itself also draws from the per-session budget (see auth.py), so
    # reconfigure with room for that plus exactly one API call.
    default_rate_limiter.reconfigure(
        global_capacity=100, global_refill_per_second=100,
        per_session_capacity=2, per_session_refill_per_second=0,
    )
    manager.get_or_login("rl-session", "u", "p")
    client = MoodleClient(manager, "rl-session", "u", "p")

    mock_post = mocker.patch("plato_mcp.moodle_client.requests.post")
    mock_post.return_value.json.return_value = {"ok": True}
    mock_post.return_value.raise_for_status.return_value = None

    client.call("core_webservice_get_site_info")  # consumes the 1 session token
    with pytest.raises(RateLimitError):
        client.call("core_webservice_get_site_info")  # session budget exhausted

    mock_post.assert_called_once()  # second call never reached the network


# ---------------------------------------------------------------------------
# Failed-login attempt cap (auth.py)
# ---------------------------------------------------------------------------


def test_failed_login_attempts_are_capped(mocker):
    manager = SessionManager()
    mocker.patch.object(manager, "_fetch_token", side_effect=AuthError("bad login"))

    for _ in range(MAX_LOGIN_ATTEMPTS):
        with pytest.raises(AuthError):
            manager.get_or_login("cap-session", "u", "wrong-password")

    # One more attempt: should be blocked WITHOUT even calling _fetch_token again.
    fetch = mocker.patch.object(manager, "_fetch_token", side_effect=AuthError("bad login"))
    with pytest.raises(AuthError, match="Too many failed login attempts"):
        manager.get_or_login("cap-session", "u", "wrong-password")
    fetch.assert_not_called()


def test_successful_login_resets_failed_attempt_counter(mocker):
    manager = SessionManager()
    mocker.patch.object(manager, "_fetch_token", side_effect=AuthError("bad login"))

    for _ in range(MAX_LOGIN_ATTEMPTS - 1):
        with pytest.raises(AuthError):
            manager.get_or_login("reset-session", "u", "wrong-password")

    mocker.patch.object(manager, "_fetch_token", return_value="tok-good")
    manager.get_or_login("reset-session", "u", "correct-password")  # succeeds, resets counter

    manager.invalidate("reset-session")
    mocker.patch.object(manager, "_fetch_token", side_effect=AuthError("bad login"))
    with pytest.raises(AuthError) as excinfo:
        manager.get_or_login("reset-session", "u", "wrong-password")
    assert "Too many failed login attempts" not in str(excinfo.value)  # budget was reset


def test_invalidate_clears_the_failed_attempt_counter(mocker):
    manager = SessionManager()
    mocker.patch.object(manager, "_fetch_token", side_effect=AuthError("bad login"))

    for _ in range(MAX_LOGIN_ATTEMPTS):
        with pytest.raises(AuthError):
            manager.get_or_login("inv-session", "u", "wrong-password")

    manager.invalidate("inv-session")

    fetch = mocker.patch.object(manager, "_fetch_token", side_effect=AuthError("bad login"))
    with pytest.raises(AuthError, match="bad login"):  # a real attempt, not the cap message
        manager.get_or_login("inv-session", "u", "wrong-password")
    fetch.assert_called_once()
