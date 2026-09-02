"""Tools: list_courses, get_course_contents (issues #12, #13)."""

from mcp.server.mcpserver import Context

from plato_mcp.context import get_client, get_userid
from plato_mcp.models import CourseSection, CourseSummary
from plato_mcp.moodle_client import MoodleClient


def list_courses_for(client: MoodleClient) -> list[CourseSummary]:
    userid = get_userid(client)
    courses = client.call("core_enrol_get_users_courses", userid=userid)
    return [CourseSummary(**c) for c in courses]


def get_course_contents_for(client: MoodleClient, course_id: int) -> list[CourseSection]:
    contents = client.call("core_course_get_contents", courseid=course_id)
    return [CourseSection(**section) for section in contents]


def register(mcp) -> None:
    @mcp.tool()
    async def list_courses(ctx: Context) -> list[CourseSummary]:
        """List the courses the logged-in PLATO account is enrolled in."""
        return list_courses_for(get_client(ctx))

    @mcp.tool()
    async def get_course_contents(course_id: int, ctx: Context) -> list[CourseSection]:
        """Get a course's weekly sections, modules, and file links."""
        return get_course_contents_for(get_client(ctx), course_id)
