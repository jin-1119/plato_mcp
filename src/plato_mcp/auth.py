"""Session/credential management for PLATO.

Design constraints (see PLAN.md / issue #10):
  - Nothing here ever writes wstoken, cookies, or passwords to disk.
  - Passwords are never stored in PlatoSession -- they're passed in fresh on
    every login/refresh call (the caller gets them from per-request config,
    e.g. Smithery's injected user config), so a retry-on-invalid-token never
    needs to remember a password across calls.
  - Sessions live in an in-memory dict keyed by an opaque session key chosen
    by the caller (the MCP transport/session id), and are evicted after
    IDLE_TTL of inactivity so nothing accumulates indefinitely.
"""

import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import requests
from bs4 import BeautifulSoup

from plato_mcp.errors import AuthError, UbboardLoginError
from plato_mcp.security import default_rate_limiter, redact

logger = logging.getLogger("plato_mcp.auth")

BASE_URL = "https://plato.pusan.ac.kr"
TOKEN_ENDPOINT = f"{BASE_URL}/login/token.php"
LOGIN_PAGE_URL = f"{BASE_URL}/login/index.php"
SERVICE = "moodle_mobile_app"
IDLE_TTL = timedelta(minutes=30)
SESSKEY_RE = re.compile(r'"sesskey":"(\w+)"')

# Cap on consecutive failed login attempts per session key, before further
# attempts are blocked without even touching the network. This is about
# protecting the PLATO *account* from looking like it's under a brute-force
# attempt, not just about our own request volume (that's what RateLimiter
# is for) -- so it's enforced separately and isn't refilled over time; it
# only clears on a successful login or an explicit invalidate().
MAX_LOGIN_ATTEMPTS = 3


@dataclass
class PlatoSession:
    username: str
    session_key: str = ""
    wstoken: str | None = None
    wstoken_obtained_at: datetime | None = None
    requests_session: requests.Session | None = None
    ubboard_sesskey: str | None = None
    last_used_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def touch(self) -> None:
        self.last_used_at = datetime.now(UTC)

    def __repr__(self) -> str:
        # Never expose wstoken/username/sesskey values, even partially, in a repr
        # that might end up in a traceback or a debug log.
        return (
            f"PlatoSession(username={redact(self.username)}, "
            f"wstoken={'<set>' if self.wstoken else None}, "
            f"has_cookie_session={self.requests_session is not None}, "
            f"ubboard_sesskey={'<set>' if self.ubboard_sesskey else None})"
        )


class SessionManager:
    """In-memory cache of PlatoSession objects, keyed by an opaque session key."""

    def __init__(
        self,
        idle_ttl: timedelta = IDLE_TTL,
        token_endpoint: str = TOKEN_ENDPOINT,
    ):
        self._cache: dict[str, PlatoSession] = {}
        self._lock = threading.Lock()
        self._idle_ttl = idle_ttl
        self._token_endpoint = token_endpoint
        self._failed_attempts: dict[str, int] = {}

    def _check_attempt_budget(self, session_key: str) -> None:
        if self._failed_attempts.get(session_key, 0) >= MAX_LOGIN_ATTEMPTS:
            raise AuthError(
                f"Too many failed login attempts ({MAX_LOGIN_ATTEMPTS}) for this session. "
                "Call invalidate() or start a fresh session before trying again."
            )

    def _record_login_failure(self, session_key: str) -> None:
        with self._lock:
            self._failed_attempts[session_key] = self._failed_attempts.get(session_key, 0) + 1

    def _record_login_success(self, session_key: str) -> None:
        with self._lock:
            self._failed_attempts.pop(session_key, None)

    def _evict_stale(self) -> None:
        now = datetime.now(UTC)
        stale_keys = [
            key for key, session in self._cache.items()
            if now - session.last_used_at > self._idle_ttl
        ]
        for key in stale_keys:
            logger.info("Evicting idle PLATO session key=%s", redact(key))
            del self._cache[key]

    def _fetch_token(self, username: str, password: str) -> str:
        """Call login/token.php. Never logs the password.

        Uses POST (data=), not GET (params=) -- Moodle accepts both, but a
        GET puts username/password in the request URL, and `requests`
        (and urllib3 below it) embeds that full URL verbatim in HTTPError/
        ConnectionError messages. A failed login would then leak the
        plaintext password into any exception message, log, or traceback
        that mentions the error. Confirmed live: a 404 against this same
        pattern with GET produced `...for url: .../x?password=SECRET123`.
        POST keeps the credentials in the body, which requests/urllib3
        never echoes back into its own error text.
        """
        try:
            resp = requests.post(
                self._token_endpoint,
                data={"username": username, "password": password, "service": SERVICE},
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning(
                "PLATO login request failed for user=%s: %s", redact(username), type(e).__name__
            )
            raise AuthError("PLATO login request failed (network or HTTP error)") from None

        data = resp.json()
        if "token" not in data:
            errorcode = data.get("errorcode", "unknown")
            logger.warning(
                "PLATO login failed for user=%s errorcode=%s", redact(username), errorcode
            )
            raise AuthError(f"PLATO login failed ({errorcode})")
        return data["token"]

    def get(self, session_key: str) -> PlatoSession | None:
        """Return the cached session if present and not evicted, else None. Never logs in."""
        with self._lock:
            self._evict_stale()
            session = self._cache.get(session_key)
            if session is not None:
                session.touch()
            return session

    def get_or_login(self, session_key: str, username: str, password: str) -> PlatoSession:
        """Return the cached session, or log in fresh if none is cached.

        Mutates an existing cache entry in place (rather than replacing it)
        so an ubboard cookie session attached by ensure_ubboard_session()
        isn't discarded if this is called afterwards.
        """
        cached = self.get(session_key)
        if cached is not None and cached.wstoken:
            return cached

        self._check_attempt_budget(session_key)
        default_rate_limiter.check(session_key)
        try:
            token = self._fetch_token(username, password)
        except AuthError:
            self._record_login_failure(session_key)
            raise
        self._record_login_success(session_key)
        with self._lock:
            session = self._cache.get(session_key)
            if session is None:
                session = PlatoSession(username=username, session_key=session_key)
                self._cache[session_key] = session
            session.wstoken = token
            session.wstoken_obtained_at = datetime.now(UTC)
            session.touch()
        return session

    def _cookie_login(self, username: str, password: str) -> tuple[requests.Session, str]:
        """Form-POST login for ubboard (cookie-session, not wstoken).

        Uses the school-SSO tab (logintab=univ) -- same credentials as the
        wstoken flow. Never logs the password. Raises UbboardLoginError on
        any failure (bad credentials, unexpected page structure, etc).
        """
        http_session = requests.Session()
        get_resp = http_session.get(LOGIN_PAGE_URL, timeout=15)
        soup = BeautifulSoup(get_resp.text, "html.parser")
        form = soup.find("form", id="form-login-sso")
        if form is None:
            raise UbboardLoginError("PLATO login page structure changed (form-login-sso missing)")
        logintoken_input = form.find("input", {"name": "logintoken"})
        logintoken = logintoken_input["value"] if logintoken_input else ""

        post_resp = http_session.post(
            LOGIN_PAGE_URL,
            data={
                "anchor": "",
                "logintoken": logintoken,
                "logintab": "univ",
                "username": username,
                "password": password,
                "rememberusername": 1,
            },
            timeout=15,
        )

        if "MoodleSession" not in http_session.cookies or "logout.php" not in post_resp.text:
            logger.warning("ubboard cookie login failed for user=%s", redact(username))
            raise UbboardLoginError("PLATO cookie-session login failed (check credentials)")

        match = SESSKEY_RE.search(post_resp.text)
        if not match:
            raise UbboardLoginError("Logged in but could not extract sesskey from the page")

        return http_session, match.group(1)

    def ensure_ubboard_session(
        self, session_key: str, username: str, password: str
    ) -> PlatoSession:
        """Ensure the cached session has a cookie session + sesskey for ubboard.

        Like get_or_login(), mutates an existing cache entry in place so a
        prior wstoken (or vice versa) isn't discarded.
        """
        cached = self.get(session_key)
        if cached is not None and cached.requests_session is not None and cached.ubboard_sesskey:
            return cached

        self._check_attempt_budget(session_key)
        default_rate_limiter.check(session_key)
        try:
            http_session, sesskey = self._cookie_login(username, password)
        except UbboardLoginError:
            self._record_login_failure(session_key)
            raise
        self._record_login_success(session_key)
        with self._lock:
            session = self._cache.get(session_key)
            if session is None:
                session = PlatoSession(username=username, session_key=session_key)
                self._cache[session_key] = session
            session.requests_session = http_session
            session.ubboard_sesskey = sesskey
            session.touch()
        return session

    def refresh(self, session_key: str, username: str, password: str) -> PlatoSession:
        """Force a brand-new login, discarding any cached session.

        Used when a webservice call fails with `invalidtoken` -- the caller
        (moodle_client.py, issue #11) catches that error, calls refresh()
        with the credentials it already has for this request, and retries
        the call once.
        """
        self.invalidate(session_key)
        return self.get_or_login(session_key, username, password)

    def require_session(self, session_key: str) -> PlatoSession:
        """Return the cached session or raise AuthError. Does not log in."""
        session = self.get(session_key)
        if session is None or not session.wstoken:
            raise AuthError("No active PLATO session for this request. Call login first.")
        return session

    def invalidate(self, session_key: str) -> None:
        with self._lock:
            self._cache.pop(session_key, None)
            self._failed_attempts.pop(session_key, None)
