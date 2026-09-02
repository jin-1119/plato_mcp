import pytest

from plato_mcp.server import mcp

EXPECTED_TOOLS = {
    # Phase 1 (official API)
    "list_courses",
    "get_course_contents",
    "list_assignments",
    "get_assignment_detail",
    "get_grades",
    "list_calendar_events",
    "get_unread_messages",
    # Phase 2 (ubboard)
    "list_notices",
    "get_notice_detail",
    "list_qna",
    "get_qna_detail",
    # Phase 3 (write)
    "submit_assignment",
}


@pytest.mark.asyncio
async def test_server_boots_with_expected_tools_registered():
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert names == EXPECTED_TOOLS
