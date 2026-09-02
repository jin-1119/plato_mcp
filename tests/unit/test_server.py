import pytest

from plato_mcp.server import mcp

EXPECTED_PHASE1_TOOLS = {
    "list_courses",
    "get_course_contents",
    "list_assignments",
    "get_assignment_detail",
    "get_grades",
    "list_calendar_events",
    "get_unread_messages",
}


@pytest.mark.asyncio
async def test_server_boots_with_phase1_tools_registered():
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert names == EXPECTED_PHASE1_TOOLS
