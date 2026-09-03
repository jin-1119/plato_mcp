"""PlatoMCPError must reach the model with its actual message intact.

Regression test for issue #60/#63: the MCP SDK's tool dispatch
(mcp.server.mcpserver.tools.base) treats a plain `Exception` as an
unanticipated crash and replaces its message with a generic "Error
executing tool <name>" before it reaches the model -- confirmed by reading
`ToolError`'s docstring and reproducing it live against a running server.
`PlatoMCPError` must inherit from the SDK's `ToolError` so every subclass
(AuthError, MoodleAPIError, RateLimitError, DownloadRejectedError,
ScrapeError, WriteConfirmationError) is treated as an anticipated failure
instead, and its message survives.
"""

from mcp.server.mcpserver.exceptions import ToolError

from plato_mcp.errors import (
    AuthError,
    MoodleAPIError,
    PlatoMCPError,
    RateLimitError,
    ScrapeError,
    UbboardLoginError,
    WriteConfirmationError,
)
from plato_mcp.files import DownloadRejectedError


def test_plato_mcp_error_is_a_tool_error():
    assert issubclass(PlatoMCPError, ToolError)


def test_all_plato_error_subclasses_are_tool_errors():
    for exc_cls in (
        AuthError,
        UbboardLoginError,
        MoodleAPIError,
        ScrapeError,
        RateLimitError,
        WriteConfirmationError,
        DownloadRejectedError,
    ):
        assert issubclass(exc_cls, ToolError), f"{exc_cls.__name__} must reach model as ToolError"


def test_rate_limit_error_message_is_preserved_as_a_plain_exception():
    # ToolError/MCPServerError add no custom __init__, so message plumbing
    # through PlatoMCPError's bases must still work exactly like a plain
    # Exception for str(exc) callers throughout the codebase.
    exc = RateLimitError("try again shortly")
    assert str(exc) == "try again shortly"
