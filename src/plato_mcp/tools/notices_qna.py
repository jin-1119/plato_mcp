"""Tools: list_notices, get_notice_detail (#22), list_qna, get_qna_detail (#23),
post_qna_question (#27).

reply_to_qna is NOT implemented -- the reply/thread POST mechanism has never
been observed (no real Q&A thread exists to reply to), so there's nothing
verified to build against. See docs/ubboard_structure.md section 6.
"""

from mcp.server.mcpserver import Context

from plato_mcp.context import get_client, get_ubboard_session
from plato_mcp.ubboard.models import UbboardPostDetail, UbboardPostSummary
from plato_mcp.ubboard.scraper import (
    find_board_id,
    get_notice_detail_for,
    get_qna_detail_for,
    list_notices_for,
    list_qna_for,
)
from plato_mcp.ubboard.writer import post_new_thread
from plato_mcp.write_tools import (
    WRITE_TOOL_ANNOTATIONS,
    WriteResult,
    default_preview_tracker,
    executed_result,
    preview_result,
)

ACTION_POST_QNA_QUESTION = "post_qna_question"


def post_qna_question_for(
    client, ubboard_session, course_id: int, subject: str, content_text: str, dry_run: bool = True
) -> WriteResult:
    """See docs/write_confirmation_pattern.md. dry_run=False is only allowed
    after a matching dry_run=True preview (same session, course_id, subject,
    content_text) -- enforced server-side via write_tools.PreviewTracker
    (issue #37), not just a docstring convention."""
    board_id = find_board_id(client, course_id, "qna")
    action_params = {"course_id": course_id, "subject": subject, "content_text": content_text}
    preview = {**action_params, "board_id": board_id}

    if dry_run:
        default_preview_tracker.record_preview(
            ubboard_session.session_key, ACTION_POST_QNA_QUESTION, action_params
        )
        return preview_result(preview, f"Q&A question '{subject}'")

    default_preview_tracker.require_previewed(
        ubboard_session.session_key, ACTION_POST_QNA_QUESTION, action_params
    )
    post_new_thread(ubboard_session, board_id, subject, content_text)
    return executed_result(preview, f"Q&A question '{subject}'")


def register(mcp) -> None:
    @mcp.tool()
    async def list_notices(course_id: int, ctx: Context) -> list[UbboardPostSummary]:
        """List announcements posted to a course's Notices board."""
        return list_notices_for(get_client(ctx), get_ubboard_session(ctx), course_id)

    @mcp.tool()
    async def get_notice_detail(
        course_id: int, post_id: int, ctx: Context
    ) -> UbboardPostDetail:
        """Get the full text of one notice/announcement."""
        return get_notice_detail_for(get_client(ctx), get_ubboard_session(ctx), course_id, post_id)

    @mcp.tool()
    async def list_qna(course_id: int, ctx: Context) -> list[UbboardPostSummary]:
        """List questions posted to a course's Q&A board."""
        return list_qna_for(get_client(ctx), get_ubboard_session(ctx), course_id)

    @mcp.tool()
    async def get_qna_detail(course_id: int, post_id: int, ctx: Context) -> UbboardPostDetail:
        """Get one Q&A question's text. Does not include replies -- see issue #23."""
        return get_qna_detail_for(get_client(ctx), get_ubboard_session(ctx), course_id, post_id)

    @mcp.tool(annotations=WRITE_TOOL_ANNOTATIONS)
    async def post_qna_question(
        course_id: int, subject: str, content_text: str, ctx: Context, dry_run: bool = True
    ) -> WriteResult:
        """Post a new question to a course's Q&A board. IRREVERSIBLE and VISIBLE
        to the instructor once dry_run=False (posted as private/secret by default).

        Call with dry_run=True (default) first, show the preview to the user, and
        only call again with dry_run=False after they explicitly confirm.
        """
        return post_qna_question_for(
            get_client(ctx), get_ubboard_session(ctx), course_id, subject, content_text, dry_run
        )
