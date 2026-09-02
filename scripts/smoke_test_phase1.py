"""Manual smoke test for Phase 1 tools against a real PLATO account.

Bypasses the MCP Context (no live client connection needed) by calling the
`*_for(client, ...)` logic functions directly with a real MoodleClient.
This is what issue #18's acceptance criteria (checklist against a real run)
is verified against; see tests/integration/README.md.
"""

from plato_mcp.auth import SessionManager
from plato_mcp.config import load_config
from plato_mcp.moodle_client import MoodleClient
from plato_mcp.tools.assignments import get_assignment_detail_for, list_assignments_for
from plato_mcp.tools.calendar import list_calendar_events_for
from plato_mcp.tools.courses import get_course_contents_for, list_courses_for
from plato_mcp.tools.grades import get_grades_for
from plato_mcp.tools.messages import get_unread_messages_for


def main():
    config = load_config()
    manager = SessionManager()
    client = MoodleClient(manager, "smoke-test", config.pnu_id, config.pnu_password)

    print("=== list_courses ===")
    courses = list_courses_for(client)
    for c in courses:
        print(f"  id={c.id} {c.fullname}")
    assert courses, "expected at least one course"

    course_id = courses[5].id if len(courses) > 5 else courses[0].id  # a real academic course

    print(f"\n=== get_course_contents(course_id={course_id}) ===")
    contents = get_course_contents_for(client, course_id)
    for section in contents:
        mod_names = [m.name for m in section.modules]
        print(f"  section '{section.name}': {mod_names}")
    assert contents, "expected at least one section"

    print(f"\n=== list_assignments(course_ids=[{course_id}]) ===")
    assignments = list_assignments_for(client, [course_id])
    print(f"  {len(assignments)} assignments: {[a.name for a in assignments]}")
    if assignments:
        detail = get_assignment_detail_for(client, course_id, assignments[0].id)
        print(f"  detail for '{detail.assignment.name}': submission={detail.submission}")
    else:
        print("  (no live assignments to test get_assignment_detail against -- structural only)")

    print(f"\n=== get_grades(course_id={course_id}) ===")
    grades = get_grades_for(client, course_id)
    print(f"  available={grades.available}, {len(grades.gradeitems)} items, message={grades.message}")
    assert grades.available or grades.message, "expected either grades or an explanation"

    print("\n=== list_calendar_events(days_ahead=30) ===")
    events = list_calendar_events_for(client, days_ahead=30)
    for e in events[:5]:
        print(f"  {e.timestart} {e.name}")
    print(f"  ({len(events)} total)")

    print("\n=== get_unread_messages ===")
    messages = get_unread_messages_for(client)
    for m in messages[:5]:
        print(f"  {m.timecreated} {m.subject}")
    print(f"  ({len(messages)} total)")

    print("\n=== Phase 1 smoke test: all 6 tools ran without crashing ===")


if __name__ == "__main__":
    main()
