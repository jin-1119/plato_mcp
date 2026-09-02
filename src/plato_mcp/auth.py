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
from plato_mcp.security import redact

logger = logging.getLogger("plato_mcp.auth")

BASE_URL = "https://plato.pusan.ac.kr"
TOKEN_ENDPOINT = f"{BASE_URL}/login/token.php"
LOGIN_PAGE_URL = f"{BASE_URL}/login/index.php"
SERVICE = "moodle_mobile_app"
IDLE_TTL = timedelta(minutes=30)
SESSKEY_RE = re.compile(r'"sesskey":"(\w+)"')


@dataclass
class PlatoSession:
    username: str
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
        """Call login/token.php. Never logs the password."""
        resp = requests.get(
            self._token_endpoint,
            params={"username": username, "password": password, "service": SERVICE},
            timeout=15,
        )
        resp.raise_for_status()
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

        token = self._fetch_token(username, password)
        with self._lock:
            session = self._cache.get(session_key)
            if session is None:
                session = PlatoSession(username=username)
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

        http_session, sesskey = self._cookie_login(username, password)
        with self._lock:
            session = self._cache.get(session_key)
            if session is None:
                session = PlatoSession(username=username)
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
