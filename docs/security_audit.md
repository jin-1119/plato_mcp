# Credential/PII log-masking audit (issue #34)

## Method

1. Grepped the entire `src/plato_mcp/` tree for `password`, `wstoken`, `sesskey` to find
   every place a secret value flows through the code, and manually reviewed each one for
   any f-string/`print`/`logger.*` call that could embed the raw value.
2. For the two `logger.*` calls found (`auth.py`, `moodle_client.py`), both already went
   through `redact()` or omitted the secret entirely (verified by existing tests in
   `tests/unit/test_auth.py`).
3. Reasoned about failure paths, not just success paths -- specifically, what happens to
   an exception's message when the underlying HTTP request itself fails.

## Finding: `requests` embeds the full request URL in failure messages

Confirmed live (see the command below) that `requests.HTTPError` (from `raise_for_status()`)
and `requests.RequestException`/`ConnectionError` (from urllib3, on connection failure)
embed the **full request URL, including the query string**, verbatim in their `str()`.
Any endpoint sending credentials or a live token as GET query params (`params=`) would
leak them into any log line, traceback, or error message that ever surfaced that exception
-- not just something we'd have to log ourselves; an unhandled exception bubbling up
through the MCP framework's own error handling would be enough.

```
$ python3 -c "
import requests
try:
    r = requests.get('https://plato.pusan.ac.kr/this/does/not/exist.php',
                      params={'username':'testuser','password':'SUPERSECRET123'}, timeout=15)
    r.raise_for_status()
except requests.RequestException as e:
    print(str(e))
"
404 Client Error: Not Found for url: https://plato.pusan.ac.kr/this/does/not/exist.php?username=testuser&password=SUPERSECRET123
```

Three call sites were vulnerable to this:

| Call site | Secret at risk | Fix |
|---|---|---|
| `auth.py::SessionManager._fetch_token` | username **and password** | Switched `requests.get(params=...)` → `requests.post(data=...)`. Confirmed live that `login/token.php` accepts POST identically. Credentials never touch the URL at all now -- not just in Python exceptions, but in any access log, proxy log, or browser-equivalent history that might ever see the request. |
| `moodle_client.py::MoodleClient._raw_call` | wstoken | Same fix: `requests.get(params=...)` → `requests.post(data=...)`. Confirmed live that `webservice/rest/server.php` accepts POST identically. |
| `files.py::download_course_file_for` | wstoken | **Cannot** switch to POST -- Moodle's `pluginfile.php` authenticates a direct file download via `?token=` in the URL, there's no POST-body equivalent for this endpoint. Instead, wrapped the request in `try/except requests.RequestException` and re-raise a sanitized message with `raise ... from None`, so the token-bearing URL never reaches an exception that could propagate or get logged. |

`from None` (not `from e`) is used in all three fixes specifically to suppress Python's
exception chaining -- otherwise `__cause__` would still hold the original, secret-bearing
exception, and anything doing full traceback formatting (an unhandled-exception printout,
`logger.exception()`, etc.) would print it anyway even though the outer message is clean.
Verified this explicitly (`excinfo.value.__cause__ is None`) in
`tests/unit/test_security_audit.py`.

## What was already safe (no change needed)

- `auth.py::SessionManager._cookie_login`'s login POST already sent `username`/`password`
  in the POST body (`data=`), not the URL -- never at risk from this specific pattern.
- `PlatoSession.__repr__` already redacts `username` and only shows `wstoken`/`ubboard_sesskey`
  as `<set>`/`None` (issue #10) -- verified again here, no regression.
- `security.py::redact()` is used consistently everywhere a session key or username needs
  to appear in a log line.

## Verification

- 6 new unit tests (`tests/unit/test_security_audit.py`, 84 total across the suite):
  regression guards confirming POST (not GET) is used for the two credential-bearing
  calls, and that a simulated `RequestException` carrying a secret-laden URL message
  never survives into the exception this codebase actually raises, for all three
  vulnerable call sites.
- Live re-verification against the real PLATO server (not mocks):
  - A wrong password (`invalidlogin` JSON response path, not an HTTP error) confirmed
    still safe as before.
  - Pointed `_fetch_token` at a nonexistent path on the real host to force a real 404
    with real credentials -- confirmed the raised `AuthError`'s message contains no
    trace of the password (`PLATO login request failed (network or HTTP error)`).
  - Confirmed the normal login + API call flow still works end-to-end over POST.

## Sign-off

Manual review of every secret-touching code path is complete; the one real finding
(URL-embedded credentials in `requests` failure messages) is fixed at all three call
sites and covered by regression tests. No further findings from this pass.
