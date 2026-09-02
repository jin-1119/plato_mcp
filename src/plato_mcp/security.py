"""Credential/PII redaction and outbound rate limiting (issue #35).

Any value that could identify or authenticate a user (username, wstoken,
session cookies, sesskey) must go through `redact()` before it touches a
log line, an exception message, or a __repr__. Passwords are never redacted
because they must never be logged at all -- there is no safe partial form.
"""

import threading
import time

from plato_mcp.errors import RateLimitError


def redact(value: str | None, keep: int = 2) -> str:
    """Return a safe-to-log form of a sensitive string.

    Keeps the first `keep` characters and masks the rest, so logs stay
    useful for correlating "which session" without exposing the secret.
    """
    if not value:
        return "<empty>"
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "*" * (len(value) - keep)


class TokenBucket:
    """Classic token bucket: `capacity` tokens, refilled at `refill_per_second`.

    Non-blocking -- try_consume() returns False immediately if empty rather
    than waiting, since this guards synchronous HTTP calls inside an async
    MCP tool handler and we don't want to stall a tool call indefinitely.
    """

    def __init__(self, capacity: float, refill_per_second: float):
        self._capacity = capacity
        self._tokens = capacity
        self._refill_per_second = refill_per_second
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def try_consume(self, amount: float = 1) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_per_second)
            self._last_refill = now
            if self._tokens >= amount:
                self._tokens -= amount
                return True
            return False


class RateLimiter:
    """Two-layer limiter: one global bucket shared by every session on this
    server process, plus one bucket per session key.

    The global bucket exists because a publicly-deployed server serves many
    MCP client sessions at once -- a per-session-only limit wouldn't stop
    the deployment as a whole from hammering PLATO if enough sessions ran
    concurrently. The per-session bucket exists because a single runaway
    agent loop within one session shouldn't be able to consume the entire
    global allowance by itself.
    """

    def __init__(
        self,
        global_capacity: float = 30,
        global_refill_per_second: float = 2,
        per_session_capacity: float = 10,
        per_session_refill_per_second: float = 0.5,
    ):
        self._global_bucket = TokenBucket(global_capacity, global_refill_per_second)
        self._per_session_capacity = per_session_capacity
        self._per_session_refill_per_second = per_session_refill_per_second
        self._session_buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def _session_bucket(self, session_key: str) -> TokenBucket:
        with self._lock:
            bucket = self._session_buckets.get(session_key)
            if bucket is None:
                bucket = TokenBucket(
                    self._per_session_capacity, self._per_session_refill_per_second
                )
                self._session_buckets[session_key] = bucket
            return bucket

    def check(self, session_key: str) -> None:
        """Raise RateLimitError if either the global or per-session budget is exhausted."""
        if not self._global_bucket.try_consume():
            raise RateLimitError(
                "PLATO request rate limit exceeded for this server (too many requests "
                "across all sessions right now) -- try again shortly."
            )
        if not self._session_bucket(session_key).try_consume():
            raise RateLimitError(
                "PLATO request rate limit exceeded for this session -- try again shortly."
            )

    def reconfigure(
        self,
        global_capacity: float | None = None,
        global_refill_per_second: float | None = None,
        per_session_capacity: float | None = None,
        per_session_refill_per_second: float | None = None,
    ) -> None:
        """Replace the bucket configuration in place (same object identity).

        Mainly for tests: modules import `default_rate_limiter` by reference
        at import time, so replacing the module-level binding in a test
        wouldn't reach those already-bound references -- reconfiguring the
        existing instance's buckets does.
        """
        with self._lock:
            if global_capacity is not None or global_refill_per_second is not None:
                old = self._global_bucket
                new_capacity = old._capacity if global_capacity is None else global_capacity
                new_refill = (
                    old._refill_per_second
                    if global_refill_per_second is None
                    else global_refill_per_second
                )
                self._global_bucket = TokenBucket(new_capacity, new_refill)
            if per_session_capacity is not None:
                self._per_session_capacity = per_session_capacity
            if per_session_refill_per_second is not None:
                self._per_session_refill_per_second = per_session_refill_per_second
            self._session_buckets.clear()


# One process-wide limiter shared by moodle_client.py and ubboard/*.py, so
# both the official-API path and the scraping path draw from the same
# global budget (see PLAN.md -- both hit the same real PLATO server).
default_rate_limiter = RateLimiter()
