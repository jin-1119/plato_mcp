"""Shared confirmation pattern for irreversible write tools.

See docs/write_confirmation_pattern.md for the full design rationale.
Every write tool (submit_assignment #25, post_qna_question/reply_to_qna #27)
returns a WriteResult and is registered with WRITE_TOOL_ANNOTATIONS.
"""

from mcp.types import ToolAnnotations
from pydantic import BaseModel

WRITE_TOOL_ANNOTATIONS = ToolAnnotations(
    destructive_hint=True,
    idempotent_hint=False,
    read_only_hint=False,
)


class WriteResult(BaseModel):
    """Standard return shape for every write tool.

    dry_run=True: `preview` describes what WOULD be submitted; nothing was
    sent to PLATO. dry_run=False: the write actually happened, `preview`
    still shows what was submitted, and `executed` is True.
    """

    dry_run: bool
    executed: bool
    preview: dict
    message: str


def preview_result(preview: dict, action_description: str) -> WriteResult:
    """Build the dry_run=True result: nothing sent, here's what would happen."""
    return WriteResult(
        dry_run=True,
        executed=False,
        preview=preview,
        message=f"Preview only -- {action_description} was NOT sent. "
        f"Call again with dry_run=False to actually send it.",
    )


def executed_result(preview: dict, action_description: str) -> WriteResult:
    """Build the dry_run=False result: the write really happened."""
    return WriteResult(
        dry_run=False,
        executed=True,
        preview=preview,
        message=f"{action_description} sent.",
    )
