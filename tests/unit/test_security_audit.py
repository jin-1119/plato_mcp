"""Issue #34: credential/PII log-masking audit.

This is the dedicated regression suite for a real vulnerability found during
the audit: `requests` embeds the full request URL -- query string included --
verbatim into HTTPError/RequestException messages on failure. Any endpoint
that sent credentials or a live token as GET query params would leak them
into any log/traceback that ever surfaced that exception.

Live repro before the fix (see PR #<issue-34> description for the exact
command): a GET with password="SUPERSECRET123" as a query param, against a
URL that 404s, raised `requests.exceptions.HTTPError` whose `str()` was:

    404 Client Error: Not Found for url: https://.../x?username=testuser&password=SUPERSECRET123

The fix: auth.py._fetch_token and moodle_client.py._raw_call now POST
credentials/wstoken in the request body instead of as GET query params (both
endpoints accept POST, confirmed live), and all three vulnerable call sites
(those two, plus files.py's download -- which must stay a GET because that's
how Moodle's pluginfile.php auth works) now catch `requests.RequestException`
and re-raise a sanitized message with `from None`, so even a connection-level
error (which also embeds the URL) can't leak the secret through this path.
"""

import pytest

from plato_mcp.auth import SessionManager
from plato_mcp.errors import AuthError, MoodleAPIError, PlatoMCPError
from plato_mcp.files import download_course_file_for
from plato_mcp.moodle_client import MoodleClient

SECRET = "SUPERSECRET123"


class FakeHTTPError(Exception):
    """Stands in for requests.HTTPError/RequestException: its message embeds
    the full request URL, exactly like the real thing does."""

    def __init__(self, url_with_secret: str):
        super().__init__(f"404 Client Error: Not Found for url: {url_with_secret}")


def test_requests_httperror_really_does_embed_url_in_its_message():
    """Not a test of our code -- documents the underlying `requests` behavior
    this whole audit is defending against, so the other tests below make sense."""
    err = FakeHTTPError(f"https://x/y?username=testuser&password={SECRET}")
    assert SECRET in str(err)


def test_fetch_token_uses_post_not_get(mocker):
    """Regression guard: if this ever regresses back to requests.get(params=...),
    the URL would carry the password again."""
    manager = SessionManager()
    mock_post = mocker.patch("plato_mcp.auth.requests.post")
    mock_get = mocker.patch("plato_mcp.auth.requests.get")
    mock_post.return_value.json.return_value = {"token": "tok"}
    mock_post.return_value.raise_for_status.return_value = None

    manager._fetch_token("someuser", SECRET)

    mock_post.assert_called_once()
    mock_get.assert_not_called()
    assert mock_post.call_args.kwargs["data"]["password"] == SECRET  # in body, not url


def test_fetch_token_request_exception_never_leaks_password(mocker):
    """Simulates what a real requests.HTTPError/ConnectionError looks like on
    failure (message embeds the full request URL) and confirms our except
    clause replaces it with a sanitized AuthError before it can propagate."""
    import requests as real_requests

    leaking_error = real_requests.exceptions.RequestException(
        f"404 Client Error: Not Found for url: https://x/token.php?username=u&password={SECRET}"
    )
    mocker.patch("plato_mcp.auth.requests.post", side_effect=leaking_error)

    manager = SessionManager()
    with pytest.raises(AuthError) as excinfo:
        manager._fetch_token("someuser", SECRET)

    assert SECRET not in str(excinfo.value)
    assert excinfo.value.__cause__ is None  # `from None` -- no chained traceback to leak through


def test_moodle_client_uses_post_not_get(mocker):
    manager = SessionManager()
    mocker.patch.object(manager, "_fetch_token", return_value="tok-abc")
    manager.get_or_login("k", "u", "p")
    client = MoodleClient(manager, "k", "u", "p")

    mock_post = mocker.patch("plato_mcp.moodle_client.requests.post")
    mock_get = mocker.patch("plato_mcp.moodle_client.requests.get")
    mock_post.return_value.json.return_value = {"ok": True}
    mock_post.return_value.raise_for_status.return_value = None

    client.call("core_webservice_get_site_info")

    mock_post.assert_called_once()
    mock_get.assert_not_called()
    assert mock_post.call_args.kwargs["data"]["wstoken"] == "tok-abc"  # in body, not url


def test_moodle_client_request_exception_never_leaks_wstoken(mocker):
    import requests as real_requests

    manager = SessionManager()
    mocker.patch.object(manager, "_fetch_token", return_value="tok-verysecret")
    manager.get_or_login("k", "u", "p")
    client = MoodleClient(manager, "k", "u", "p")

    leaking_error = real_requests.exceptions.RequestException(
        "404 Client Error: Not Found for url: "
        "https://x/server.php?wstoken=tok-verysecret&wsfunction=core_webservice_get_site_info"
    )
    mocker.patch("plato_mcp.moodle_client.requests.post", side_effect=leaking_error)

    with pytest.raises(MoodleAPIError) as excinfo:
        client.call("core_webservice_get_site_info")

    assert "tok-verysecret" not in str(excinfo.value)
    assert excinfo.value.__cause__ is None


def test_download_request_exception_never_leaks_wstoken(mocker, tmp_path):
    import requests as real_requests

    client = mocker.Mock()
    client.get_wstoken.return_value = "tok-verysecret"

    leaking_error = real_requests.exceptions.RequestException(
        "404 Client Error: Not Found for url: https://x/f.pdf?token=tok-verysecret"
    )
    mocker.patch("plato_mcp.files.requests.get", side_effect=leaking_error)

    with pytest.raises(PlatoMCPError) as excinfo:
        download_course_file_for(client, "https://x/f.pdf", str(tmp_path / "f.pdf"))

    assert "tok-verysecret" not in str(excinfo.value)
    assert excinfo.value.__cause__ is None
