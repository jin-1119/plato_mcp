"""Typed exceptions for plato-mcp, mapped to clean MCP-facing error messages."""


class PlatoMCPError(Exception):
    """Base class for all plato-mcp errors."""


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
