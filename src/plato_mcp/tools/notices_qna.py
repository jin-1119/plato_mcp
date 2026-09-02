"""Tools: list_notices, get_notice_detail (issue #22), list_qna, get_qna_detail (issue #23)."""

from mcp.server.mcpserver import Context

from plato_mcp.context import get_client, get_ubboard_session
from plato_mcp.ubboard.models import UbboardPostDetail, UbboardPostSummary
from plato_mcp.ubboard.scraper import (
    get_notice_detail_for,
    get_qna_detail_for,
    list_notices_for,
    list_qna_for,
)


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
