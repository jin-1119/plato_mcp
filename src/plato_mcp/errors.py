"""Typed exceptions for plato-mcp, mapped to clean MCP-facing error messages."""

from mcp.server.mcpserver.exceptions import ToolError


class PlatoMCPError(ToolError):
    """Base class for all plato-mcp errors.

    Inherits from the SDK's `ToolError` (an "anticipated failure" marker),
    not plain `Exception` -- confirmed by reading `ToolError`'s docstring
    (mcp/server/mcpserver/exceptions.py) and reproducing it live (issue
    #60/#63 review): the SDK's tool dispatch (tools/base.py) treats any
    plain `Exception` as an unanticipated crash and replaces its message
    with a generic "Error executing tool <name>" before it reaches the
    model -- our carefully-written, security-reviewed error text (e.g.
    RateLimitError's "try again shortly", or the sanitized download-failure
    messages in files.py) was being silently discarded. `ToolError` (and
    subclasses, which every exception below is) instead reaches the model
    as `is_error=True` with the actual message intact. This one change
    fixes every `PlatoMCPError` subclass at once, not just RateLimitError."""


class AuthError(PlatoMCPError):
    """Login to PLATO failed, or no active session exists."""


class UbboardLoginError(AuthError):
    """Cookie-session login (for ubboard scraping) failed -- distinct from a
    wstoken (official API) login failure, since it's a different auth path
    against a different endpoint."""


class MoodleAPIError(PlatoMCPError):
    """A Moodle webservice call returned an error envelope."""

    def __init__(self, message: str, errorcode: str | None = None):
        super().__init__(message)
        self.errorcode = errorcode


class ScrapeError(PlatoMCPError):
    """ubboard HTML could not be parsed as expected."""


class RateLimitError(PlatoMCPError):
    """Outbound request throttled to protect PLATO from abuse."""


class WriteConfirmationError(PlatoMCPError):
    """dry_run=False was called without a matching, still-fresh dry_run=True
    preview for the same action (see docs/write_confirmation_pattern.md and
    the issue #37 abuse-prevention review)."""
