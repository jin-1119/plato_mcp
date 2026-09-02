"""Shared confirmation pattern for irreversible write tools.

See docs/write_confirmation_pattern.md for the full design rationale.
Every write tool (submit_assignment #25, post_qna_question #27) returns a
WriteResult and is registered with WRITE_TOOL_ANNOTATIONS.

PreviewTracker (issue #37, abuse-prevention review) closes the gap that
design doc explicitly left open: originally, dry_run was only a *convention*
-- nothing stopped an MCP client or an unusually eager LLM from calling
dry_run=False on the very first try, skipping the preview entirely.
PreviewTracker makes it enforced: dry_run=False for a given action now
requires a matching dry_run=True preview (same session, same action, same
parameters) to have happened first, within the last PREVIEW_TTL_SECONDS.
"""

import hashlib
import json
import threading
import time

from mcp.types import ToolAnnotations
from pydantic import BaseModel

from plato_mcp.errors import WriteConfirmationError

WRITE_TOOL_ANNOTATIONS = ToolAnnotations(
    destructive_hint=True,
    idempotent_hint=False,
    read_only_hint=False,
)

PREVIEW_TTL_SECONDS = 300  # 5 minutes to go from preview to confirm


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
        f"Call again with dry_run=False (same parameters) to actually send it.",
    )


def executed_result(preview: dict, action_description: str) -> WriteResult:
    """Build the dry_run=False result: the write really happened."""
    return WriteResult(
        dry_run=False,
        executed=True,
        preview=preview,
        message=f"{action_description} sent.",
    )


class PreviewTracker:
    """Requires dry_run=True to have happened, with matching parameters,
    before the matching dry_run=False is allowed to proceed.

    Keyed on (session_key, action_name, hash of the action's own parameters)
    so a preview for one assignment/question can't be used to wave through a
    confirm for a *different* one -- the confirm has to match exactly what
    was actually previewed and shown to the user.
    """

    def __init__(self, ttl_seconds: float = PREVIEW_TTL_SECONDS):
        self._ttl = ttl_seconds
        self._previews: dict[str, float] = {}  # key -> expiry (time.monotonic())
        self._lock = threading.Lock()

    @staticmethod
    def _key(session_key: str, action: str, params: dict) -> str:
        payload = json.dumps(params, sort_keys=True, default=str)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"{session_key}:{action}:{digest}"

    def record_preview(self, session_key: str, action: str, params: dict) -> None:
        key = self._key(session_key, action, params)
        with self._lock:
            self._previews[key] = time.monotonic() + self._ttl

    def require_previewed(self, session_key: str, action: str, params: dict) -> None:
        """Raise WriteConfirmationError unless a matching preview is on file
        and not yet expired. Consumes the preview on success -- one preview
        authorizes exactly one confirm, not repeated ones."""
        key = self._key(session_key, action, params)
        with self._lock:
            expiry = self._previews.get(key)
            if expiry is None or expiry < time.monotonic():
                raise WriteConfirmationError(
                    f"No matching preview found for this {action} (or it expired -- "
                    f"previews are valid for {int(self._ttl)}s). Call with dry_run=True "
                    "first, using the exact same parameters, before dry_run=False."
                )
            del self._previews[key]

    def clear(self) -> None:
        """Mainly for tests."""
        with self._lock:
            self._previews.clear()


default_preview_tracker = PreviewTracker()
