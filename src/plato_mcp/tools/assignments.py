"""Tools: list_assignments, get_assignment_detail (issue #14)."""

from datetime import UTC, datetime

from mcp.server.mcpserver import Context

from plato_mcp.context import get_client, get_userid
from plato_mcp.models import (
    AssignmentDetail,
    AssignmentExtraData,
    AssignmentSummary,
    PreviousAttempt,
    SubmissionFeedback,
    SubmissionStatus,
)
from plato_mcp.moodle_client import MoodleClient


def list_assignments_for(client: MoodleClient, course_ids: list[int]) -> list[AssignmentSummary]:
    result = client.call("mod_assign_get_assignments", courseids=course_ids)
    summaries: list[AssignmentSummary] = []
    for course in result.get("courses", []):
        for assignment in course.get("assignments", []):
            summaries.append(AssignmentSummary(**{**assignment, "courseid": course.get("id")}))
    return summaries


def get_assignment_detail_for(
    client: MoodleClient, course_id: int, assignment_id: int
) -> AssignmentDetail:
    assignments = list_assignments_for(client, [course_id])
    match = next((a for a in assignments if a.id == assignment_id), None)
    if match is None:
        raise ValueError(f"Assignment {assignment_id} not found in course {course_id}")

    userid = get_userid(client)
    status = client.call("mod_assign_get_submission_status", assignid=assignment_id, userid=userid)

    lastattempt = status.get("lastattempt") or {}
    submission_raw = lastattempt.get("submission")

    submission = None
    if submission_raw:
        timemodified = submission_raw.get("timemodified")
        late = bool(
            timemodified
            and match.duedate
            and datetime.fromtimestamp(timemodified, tz=UTC) > match.duedate
        )
        submission = SubmissionStatus(
            submitted=submission_raw.get("status") == "submitted",
            status=submission_raw.get("status"),
            late=late,
            timemodified=timemodified,
            cansubmit=lastattempt.get("cansubmit"),
            locked=lastattempt.get("locked"),
            extensionduedate=lastattempt.get("extensionduedate"),
            gradingstatus=lastattempt.get("gradingstatus"),
        )

    feedback_raw = status.get("feedback")
    feedback = SubmissionFeedback(**feedback_raw) if feedback_raw else None

    previousattempts = [
        PreviousAttempt(**attempt) for attempt in (status.get("previousattempts") or [])
    ]

    assignmentdata_raw = status.get("assignmentdata")
    extra = AssignmentExtraData(**assignmentdata_raw) if assignmentdata_raw else None

    return AssignmentDetail(
        assignment=match,
        submission=submission,
        feedback=feedback,
        previousattempts=previousattempts,
        extra=extra,
    )


def register(mcp) -> None:
    @mcp.tool()
    async def list_assignments(course_ids: list[int], ctx: Context) -> list[AssignmentSummary]:
        """List assignments across one or more courses, with due dates."""
        return list_assignments_for(get_client(ctx), course_ids)

    @mcp.tool()
    async def get_assignment_detail(
        course_id: int, assignment_id: int, ctx: Context
    ) -> AssignmentDetail:
        """Get one assignment's details and this account's submission status."""
        return get_assignment_detail_for(get_client(ctx), course_id, assignment_id)
