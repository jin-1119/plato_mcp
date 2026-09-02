"""Generic caller for PLATO's Moodle webservice REST API.

Wraps `webservice/rest/server.php`. Every official-API tool (Phase 1: courses,
contents, assignments, grades, calendar, messages) goes through this one
`MoodleClient.call()` rather than each having its own HTTP logic.
"""

import logging

import requests

from plato_mcp.auth import SessionManager
from plato_mcp.errors import MoodleAPIError

logger = logging.getLogger("plato_mcp.moodle_client")

BASE_URL = "https://plato.pusan.ac.kr"
REST_ENDPOINT = f"{BASE_URL}/webservice/rest/server.php"


def flatten_params(params: dict) -> dict:
    """Expand list/dict-valued params into Moodle's bracket notation.

    e.g. flatten_params({"courseids": [1, 2]}) ->
         {"courseids[0]": 1, "courseids[1]": 2}
    """
    flat: dict = {}
    for key, value in params.items():
        if isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    for subkey, subval in item.items():
                        flat[f"{key}[{i}][{subkey}]"] = subval
                else:
                    flat[f"{key}[{i}]"] = item
        else:
            flat[key] = value
    return flat


def _is_error_envelope(result: object) -> bool:
    return isinstance(result, dict) and "errorcode" in result


class MoodleClient:
    """Calls Moodle webservice functions for one PLATO session, with a
    single transparent retry when the cached wstoken has gone stale."""

    def __init__(
        self,
        session_manager: SessionManager,
        session_key: str,
        username: str,
        password: str,
        rest_endpoint: str = REST_ENDPOINT,
        timeout: int = 15,
    ):
        self._session_manager = session_manager
        self._session_key = session_key
        self._username = username
        self._password = password
        self._rest_endpoint = rest_endpoint
        self._timeout = timeout

    def get_wstoken(self) -> str:
        """Ensure a logged-in session and return its wstoken.

        Used by files.py to build an authenticated pluginfile.php download
        URL (?token={wstoken}) -- that's not a webservice function call, so
        it doesn't go through call()/_raw_call(), but it needs the same
        cached-or-login session.
        """
        session = self._session_manager.get_or_login(
            self._session_key, self._username, self._password
        )
        return session.wstoken

    def call(self, wsfunction: str, **params) -> dict | list:
        session = self._session_manager.get_or_login(
            self._session_key, self._username, self._password
        )
        result = self._raw_call(session.wstoken, wsfunction, params)

        if _is_error_envelope(result) and result.get("errorcode") == "invalidtoken":
            logger.info("wstoken invalid for wsfunction=%s, refreshing once", wsfunction)
            session = self._session_manager.refresh(
                self._session_key, self._username, self._password
            )
            result = self._raw_call(session.wstoken, wsfunction, params)

        if _is_error_envelope(result):
            errorcode = result.get("errorcode")
            message = result.get("message") or result.get("error") or "Moodle API error"
            raise MoodleAPIError(message, errorcode=errorcode)

        return result

    def _raw_call(self, wstoken: str, wsfunction: str, params: dict) -> dict | list:
        query = {"wstoken": wstoken, "wsfunction": wsfunction, "moodlewsrestformat": "json"}
        query.update(flatten_params(params))
        resp = requests.get(self._rest_endpoint, params=query, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()
