"""Credential/PII redaction helpers.

Any value that could identify or authenticate a user (username, wstoken,
session cookies, sesskey) must go through `redact()` before it touches a
log line, an exception message, or a __repr__. Passwords are never redacted
because they must never be logged at all -- there is no safe partial form.
"""


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
