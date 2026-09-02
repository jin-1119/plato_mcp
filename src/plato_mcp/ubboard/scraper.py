"""HTTP fetching + board resolution for ubboard (read side).

Pairs with parser.py: this module does the network calls and hands raw
HTML to the pure parser functions. Course-contents (official API) tells us
which ubboard module id is the Notices board vs Q&A board -- see
docs/ubboard_structure.md section 2.
"""

import json

from plato_mcp.auth import PlatoSession
from plato_mcp.errors import ScrapeError
from plato_mcp.moodle_client import MoodleClient
from plato_mcp.security import default_rate_limiter
from plato_mcp.ubboard.models import UbboardPostDetail, UbboardPostSummary
from plato_mcp.ubboard.parser import parse_detail_page, parse_list_page

BASE_URL = "https://plato.pusan.ac.kr"


def find_board_id(client: MoodleClient, course_id: int, board_type: str) -> int:
    """Find the ubboard module id for `board_type` ("notice" or "qna") in a course."""
    contents = client.call("core_course_get_contents", courseid=course_id)
    for section in contents:
        for module in section.get("modules", []):
            if module.get("modname") != "ubboard":
                continue
            try:
                custom = json.loads(module.get("customdata") or "{}")
            except json.JSONDecodeError:
                continue
            if custom.get("type") == board_type:
                return module["id"]
    raise ScrapeError(f"No ubboard board of type={board_type!r} found in course {course_id}")


def fetch_list_html(session: PlatoSession, board_id: int) -> str:
    # listsize=0 asks ubboard for every post on one page ("All" in the UI),
    # sidestepping page-by-page pagination entirely -- see docs/ubboard_structure.md
    # section 3. Fine at this project's scale (course boards, not forums).
    default_rate_limiter.check(session.session_key)
    resp = session.requests_session.get(
        f"{BASE_URL}/mod/ubboard/view.php",
        params={"id": board_id, "listsize": 0},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.text


def fetch_detail_html(session: PlatoSession, board_id: int, post_id: int) -> str:
    default_rate_limiter.check(session.session_key)
    resp = session.requests_session.get(
        f"{BASE_URL}/mod/ubboard/article.php",
        params={"id": board_id, "bwid": post_id},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.text


def list_notices_for(
    client: MoodleClient, session: PlatoSession, course_id: int
) -> list[UbboardPostSummary]:
    board_id = find_board_id(client, course_id, "notice")
    html = fetch_list_html(session, board_id)
    return parse_list_page(html, board_id)


def get_notice_detail_for(
    client: MoodleClient, session: PlatoSession, course_id: int, post_id: int
) -> UbboardPostDetail:
    board_id = find_board_id(client, course_id, "notice")
    html = fetch_detail_html(session, board_id, post_id)
    return parse_detail_page(html, board_id, post_id)


def list_qna_for(
    client: MoodleClient, session: PlatoSession, course_id: int
) -> list[UbboardPostSummary]:
    board_id = find_board_id(client, course_id, "qna")
    html = fetch_list_html(session, board_id)
    return parse_list_page(html, board_id)


def get_qna_detail_for(
    client: MoodleClient, session: PlatoSession, course_id: int, post_id: int
) -> UbboardPostDetail:
    """Get one Q&A question's title/writer/date/content.

    Does NOT include replies -- no real Q&A thread has ever been observed on
    any enrolled course (checked live, see docs/ubboard_structure.md section
    5), so there is no verified reply markup to parse. `content_html` is
    just the original question's body, same as a Notices post. Revisit once
    a real Q&A thread with replies exists.
    """
    board_id = find_board_id(client, course_id, "qna")
    html = fetch_detail_html(session, board_id, post_id)
    return parse_detail_page(html, board_id, post_id)
