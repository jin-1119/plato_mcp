"""Issue #37: abuse-prevention review for write tools before public listing.

The gap docs/write_confirmation_pattern.md explicitly left open: dry_run was
only a convention, nothing stopped a client/LLM from calling dry_run=False on
the very first try. write_tools.PreviewTracker closes it. These tests confirm
it's actually enforced at the tool level (assignments.submit_assignment_for,
notices_qna.post_qna_question_for), not just in the tracker class itself
(that's covered separately below too).
"""

import json

import pytest

from plato_mcp.errors import WriteConfirmationError
from plato_mcp.tools.assignments import submit_assignment_for
from plato_mcp.tools.notices_qna import post_qna_question_for
from plato_mcp.write_tools import PreviewTracker, default_preview_tracker

# ---------------------------------------------------------------------------
# PreviewTracker unit behavior (isolated instance)
# ---------------------------------------------------------------------------


def test_require_previewed_fails_with_no_prior_preview():
    tracker = PreviewTracker()
    with pytest.raises(WriteConfirmationError):
        tracker.require_previewed("session-1", "some_action", {"x": 1})


def test_require_previewed_succeeds_after_matching_preview():
    tracker = PreviewTracker()
    tracker.record_preview("session-1", "some_action", {"x": 1})
    tracker.require_previewed("session-1", "some_action", {"x": 1})  # no raise


def test_require_previewed_fails_if_params_dont_match():
    tracker = PreviewTracker()
    tracker.record_preview("session-1", "some_action", {"x": 1})
    with pytest.raises(WriteConfirmationError):
        tracker.require_previewed("session-1", "some_action", {"x": 2})  # different params


def test_require_previewed_fails_if_session_differs():
    """A preview shown to one MCP session can't authorize a confirm from a
    different one -- important if a server process ever handles concurrent
    sessions from different users."""
    tracker = PreviewTracker()
    tracker.record_preview("session-1", "some_action", {"x": 1})
    with pytest.raises(WriteConfirmationError):
        tracker.require_previewed("session-2", "some_action", {"x": 1})


def test_require_previewed_fails_if_action_differs():
    tracker = PreviewTracker()
    tracker.record_preview("session-1", "submit_assignment", {"x": 1})
    with pytest.raises(WriteConfirmationError):
        tracker.require_previewed("session-1", "post_qna_question", {"x": 1})


def test_preview_is_consumed_by_one_confirm_not_reusable():
    """Prevents replaying a single confirmed preview as an implicit
    authorization to keep re-submitting the same action indefinitely."""
    tracker = PreviewTracker()
    tracker.record_preview("session-1", "some_action", {"x": 1})
    tracker.require_previewed("session-1", "some_action", {"x": 1})  # consumes it
    with pytest.raises(WriteConfirmationError):
        tracker.require_previewed("session-1", "some_action", {"x": 1})  # gone now


def test_expired_preview_is_rejected(mocker):
    tracker = PreviewTracker(ttl_seconds=60)
    tracker.record_preview("session-1", "some_action", {"x": 1})

    import time

    mocker.patch("time.monotonic", return_value=time.monotonic() + 61)
    with pytest.raises(WriteConfirmationError, match="expired"):
        tracker.require_previewed("session-1", "some_action", {"x": 1})


def test_key_is_order_independent_across_dict_key_order():
    """Params dict key order shouldn't matter for matching (json.dumps sorts keys)."""
    tracker = PreviewTracker()
    tracker.record_preview("s", "a", {"a": 1, "b": 2})
    tracker.require_previewed("s", "a", {"b": 2, "a": 1})  # same content, different order


# ---------------------------------------------------------------------------
# Wired into the actual write tools (assignments.py, notices_qna.py)
# ---------------------------------------------------------------------------


def test_submit_assignment_confirm_without_preview_is_rejected(mocker):
    client = mocker.Mock()
    client.session_key = "sess-abuse-1"
    client.call.return_value = {"courses": [{"id": 1, "assignments": [{"id": 1, "name": "HW"}]}]}

    with pytest.raises(WriteConfirmationError):
        submit_assignment_for(client, course_id=1, assignment_id=1, text="answer", dry_run=False)

    # Never reached the actual submission call.
    submit_calls = [
        c for c in client.call.call_args_list if c.args[0] == "mod_assign_save_submission"
    ]
    assert submit_calls == []


def test_submit_assignment_confirm_with_different_text_than_previewed_is_rejected(mocker):
    """An adversarial client can't preview a benign submission and then
    confirm a different (e.g. malicious) one under cover of that preview."""
    client = mocker.Mock()
    client.session_key = "sess-abuse-2"
    client.call.return_value = {"courses": [{"id": 1, "assignments": [{"id": 1, "name": "HW"}]}]}

    submit_assignment_for(client, course_id=1, assignment_id=1, text="benign preview")

    with pytest.raises(WriteConfirmationError):
        submit_assignment_for(
            client, course_id=1, assignment_id=1, text="DIFFERENT TEXT", dry_run=False
        )


def test_post_qna_question_confirm_without_preview_is_rejected(mocker):
    client = mocker.Mock()
    client.call.return_value = [
        {
            "id": 1,
            "modules": [
                {
                    "id": 99,
                    "modname": "ubboard",
                    "customdata": json.dumps({"type": "qna"}),
                }
            ],
        }
    ]
    session = mocker.Mock()
    session.session_key = "sess-abuse-3"

    with pytest.raises(WriteConfirmationError):
        post_qna_question_for(
            client, session, course_id=1, subject="Q", content_text="body", dry_run=False
        )

    session.requests_session.post.assert_not_called()


def test_default_preview_tracker_is_the_one_actually_used_by_the_tools(mocker):
    """Sanity check that the tools go through the process-wide singleton
    (so a preview really is visible to a later, separate confirm call in
    real usage), not a private tracker each tool made up on its own."""
    client = mocker.Mock()
    client.session_key = "sess-abuse-4"
    client.call.return_value = {"courses": [{"id": 1, "assignments": [{"id": 1, "name": "HW"}]}]}

    submit_assignment_for(client, course_id=1, assignment_id=1, text="answer")

    # If this were a different tracker instance, this direct check would fail.
    default_preview_tracker.require_previewed(
        "sess-abuse-4",
        "submit_assignment",
        {"course_id": 1, "assignment_id": 1, "text": "answer"},
    )
