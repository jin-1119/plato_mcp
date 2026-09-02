"""Unit tests for Phase 1 tool logic functions.

These test the `*_for(client, ...)` functions directly against a mocked
MoodleClient, bypassing the MCP Context entirely -- the Context is just
plumbing for the session key (see context.py) and isn't part of the
business logic being tested here.
"""

from datetime import UTC, datetime, timedelta

import pytest

from plato_mcp.errors import MoodleAPIError
from plato_mcp.tools.assignments import get_assignment_detail_for, list_assignments_for
from plato_mcp.tools.calendar import list_calendar_events_for
from plato_mcp.tools.courses import get_course_contents_for, list_courses_for
from plato_mcp.tools.grades import get_grades_for
from plato_mcp.tools.messages import get_unread_messages_for


@pytest.fixture
def mock_client(mocker):
    client = mocker.Mock()
    return client


def _epoch(dt: datetime) -> int:
    return int(dt.timestamp())


def test_list_courses_for(mock_client):
    start = datetime(2026, 9, 1, tzinfo=UTC)
    end = datetime(2026, 12, 20, tzinfo=UTC)
    mock_client.call.side_effect = lambda fn, **kw: (
        {"userid": 448520}
        if fn == "core_webservice_get_site_info"
        else [
            {
                "id": 6253,
                "fullname": "거시경제학",
                "shortname": "MACRO",
                "visible": 1,
                "startdate": _epoch(start),
                "enddate": _epoch(end),
                "extra": "ignored",
            },
            {
                "id": 12633,
                "fullname": "[25.동계] 영어연수 단기파견",
                "shortname": "WINTER",
                "visible": 1,
                "startdate": _epoch(datetime(2025, 12, 1, tzinfo=UTC)),
                "enddate": 0,  # Moodle's "no end date set"
            },
        ]
    )
    result = list_courses_for(mock_client)
    assert len(result) == 2
    assert result[0].id == 6253
    assert result[0].fullname == "거시경제학"
    assert result[0].startdate == start
    assert result[0].enddate == end
    assert result[1].enddate is None  # 0 -> None, not epoch-zero datetime


def test_get_course_contents_for(mock_client):
    mock_client.call.return_value = [
        {
            "id": 1,
            "name": "Week 1",
            "modules": [
                {
                    "id": 100,
                    "name": "Syllabus",
                    "modname": "resource",
                    "url": "https://plato.pusan.ac.kr/mod/resource/view.php?id=100",
                    "completiondata": {"isoverallcomplete": True},
                    "contents": [
                        {
                            "filename": "syllabus.pdf",
                            "fileurl": "https://x/f.pdf",
                            "filesize": 1000,
                            "mimetype": "application/pdf",
                            "author": "안영빈",
                            "timemodified": _epoch(datetime(2026, 9, 1, tzinfo=UTC)),
                        }
                    ],
                }
            ],
        }
    ]
    result = get_course_contents_for(mock_client, course_id=6253)
    assert len(result) == 1
    file_entry = result[0].modules[0].contents[0]
    assert file_entry.filename == "syllabus.pdf"
    assert file_entry.needs_token is True
    assert file_entry.mimetype == "application/pdf"
    assert file_entry.author == "안영빈"
    assert file_entry.timemodified == datetime(2026, 9, 1, tzinfo=UTC)
    assert result[0].modules[0].completed is True


def test_get_course_contents_for_completed_missing_when_no_completiondata(mock_client):
    mock_client.call.return_value = [
        {
            "id": 1,
            "name": "Week 1",
            "modules": [{"id": 100, "name": "Syllabus", "modname": "resource", "contents": []}],
        }
    ]
    result = get_course_contents_for(mock_client, course_id=6253)
    assert result[0].modules[0].completed is None


def test_list_assignments_for_flattens_courses(mock_client):
    mock_client.call.return_value = {
        "courses": [
            {
                "id": 6253,
                "assignments": [
                    {"id": 1, "name": "HW1", "duedate": _epoch(datetime(2026, 10, 1, tzinfo=UTC))},
                ],
            }
        ],
        "warnings": [],
    }
    result = list_assignments_for(mock_client, [6253])
    assert len(result) == 1
    assert result[0].courseid == 6253
    assert result[0].duedate == datetime(2026, 10, 1, tzinfo=UTC)


def test_get_assignment_detail_for_not_submitted(mock_client):
    due = datetime(2026, 10, 1, tzinfo=UTC)

    def fake_call(fn, **kw):
        if fn == "mod_assign_get_assignments":
            return {
                "courses": [
                    {"id": 6253, "assignments": [{"id": 1, "name": "HW1", "duedate": _epoch(due)}]}
                ]
            }
        if fn == "core_webservice_get_site_info":
            return {"userid": 448520}
        if fn == "mod_assign_get_submission_status":
            return {"lastattempt": {"submission": None}}
        raise AssertionError(f"unexpected call: {fn}")

    mock_client.call.side_effect = fake_call
    detail = get_assignment_detail_for(mock_client, course_id=6253, assignment_id=1)
    assert detail.assignment.name == "HW1"
    assert detail.submission is None


def test_get_assignment_detail_for_late_submission(mock_client):
    due = datetime(2026, 10, 1, tzinfo=UTC)
    submitted_late = datetime(2026, 10, 2, tzinfo=UTC)

    def fake_call(fn, **kw):
        if fn == "mod_assign_get_assignments":
            return {
                "courses": [
                    {"id": 6253, "assignments": [{"id": 1, "name": "HW1", "duedate": _epoch(due)}]}
                ]
            }
        if fn == "core_webservice_get_site_info":
            return {"userid": 448520}
        if fn == "mod_assign_get_submission_status":
            return {
                "lastattempt": {
                    "submission": {"status": "submitted", "timemodified": _epoch(submitted_late)}
                }
            }
        raise AssertionError(f"unexpected call: {fn}")

    mock_client.call.side_effect = fake_call
    detail = get_assignment_detail_for(mock_client, course_id=6253, assignment_id=1)
    assert detail.submission.submitted is True
    assert detail.submission.late is True


def test_get_assignment_detail_for_unknown_id_raises(mock_client):
    mock_client.call.return_value = {"courses": [{"id": 6253, "assignments": []}]}
    with pytest.raises(ValueError):
        get_assignment_detail_for(mock_client, course_id=6253, assignment_id=999)


def test_get_grades_for_available(mock_client):
    def fake_call(fn, **kw):
        if fn == "core_webservice_get_site_info":
            return {"userid": 448520}
        item = {
            "id": 1,
            "itemname": "출석",
            "itemtype": "manual",
            "graderaw": 10.0,
            "grademin": 0.0,
            "grademax": 100.0,
            "feedback": "잘했습니다",
        }
        return {"usergrades": [{"gradeitems": [item]}]}

    mock_client.call.side_effect = fake_call
    result = get_grades_for(mock_client, course_id=6253)
    assert result.available is True
    assert result.gradeitems[0].graderaw == 10.0
    assert result.gradeitems[0].grademax == 100.0
    assert result.gradeitems[0].feedback == "잘했습니다"


def test_get_grades_for_no_permission(mock_client):
    def fake_call(fn, **kw):
        if fn == "core_webservice_get_site_info":
            return {"userid": 448520}
        raise MoodleAPIError("No permission", errorcode="nopermissiontoviewgrades")

    mock_client.call.side_effect = fake_call
    result = get_grades_for(mock_client, course_id=12633)
    assert result.available is False
    assert result.gradeitems == []


def test_get_grades_for_other_error_propagates(mock_client):
    def fake_call(fn, **kw):
        if fn == "core_webservice_get_site_info":
            return {"userid": 448520}
        raise MoodleAPIError("boom", errorcode="somethingelse")

    mock_client.call.side_effect = fake_call
    with pytest.raises(MoodleAPIError):
        get_grades_for(mock_client, course_id=6253)


def test_list_calendar_events_sorted_chronologically(mock_client):
    now = datetime.now(UTC)
    later = _epoch(now + timedelta(days=5))
    earlier = _epoch(now + timedelta(days=2))
    past = _epoch(now - timedelta(days=1))
    mock_client.call.return_value = {
        "events": [
            {"id": 1, "name": "Later", "timestart": later},
            {"id": 2, "name": "Earlier", "timestart": earlier},
            {"id": 3, "name": "Past", "timestart": past},
        ]
    }
    result = list_calendar_events_for(mock_client, days_ahead=14)
    assert [e.name for e in result] == ["Earlier", "Later"]  # past event filtered out


def test_list_calendar_events_excludes_events_beyond_window(mock_client):
    now = datetime.now(UTC)
    within = _epoch(now + timedelta(days=5))
    beyond = _epoch(now + timedelta(days=20))
    mock_client.call.return_value = {
        "events": [
            {"id": 1, "name": "Within", "timestart": within, "description": "<p>hi</p>"},
            {"id": 2, "name": "Beyond", "timestart": beyond},
        ]
    }
    result = list_calendar_events_for(mock_client, days_ahead=14)
    assert [e.name for e in result] == ["Within"]
    assert result[0].description == "<p>hi</p>"


def test_get_unread_messages_for(mock_client):
    def fake_call(fn, **kw):
        if fn == "core_webservice_get_site_info":
            return {"userid": 448520}
        assert kw["read"] == 0
        return {
            "messages": [
                {
                    "id": 1,
                    "useridfrom": -10,
                    "userfromfullname": "PLATO",
                    "subject": "새 로그인",
                    "eventtype": "newlogin",
                }
            ]
        }

    mock_client.call.side_effect = fake_call
    result = get_unread_messages_for(mock_client)
    assert result[0].userfromfullname == "PLATO"
    assert result[0].eventtype == "newlogin"
    assert len(result) == 1
    assert result[0].subject == "새 로그인"
