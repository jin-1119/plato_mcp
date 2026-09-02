"""CSRF/sesskey POST handling for ubboard writes (Q&A question/reply, issue #27).

Not used for Notices -- students can't post there (instructor-only board,
confirmed in #19: no "Write" link appears on a Notices board for this
account, only on Q&A boards).

The write form embeds two per-page-load random draft-area ids
(content[itemid], attachment) that Moodle's rich-text editor and file
picker need -- these must be scraped fresh from a GET of write.php each
time, never hardcoded or reused across requests (see
docs/ubboard_structure.md section 6).
"""

from bs4 import BeautifulSoup

from plato_mcp.auth import PlatoSession
from plato_mcp.errors import ScrapeError
from plato_mcp.security import default_rate_limiter

BASE_URL = "https://plato.pusan.ac.kr"
WRITE_FORM_ID = "mformubboard"

# The write form's "secret" checkbox (private/visible-to-instructor-only post)
# defaults to checked in the live form -- keep that default here too, since a
# question directed at an instructor shouldn't default to being visible to
# classmates.
DEFAULT_SECRET = 1


def _fetch_write_form_tokens(session: PlatoSession, board_id: int) -> dict:
    default_rate_limiter.check(session.session_key)
    resp = session.requests_session.get(
        f"{BASE_URL}/mod/ubboard/write.php", params={"id": board_id}, timeout=15
    )
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    form = soup.find("form", id=WRITE_FORM_ID)
    if form is None:
        raise ScrapeError(f"ubboard write form (#{WRITE_FORM_ID}) not found -- page changed?")

    def field(name: str) -> str:
        el = form.find(["input", "textarea"], {"name": name})
        if el is None:
            raise ScrapeError(f"ubboard write form missing expected field: {name!r}")
        return el.get("value", "")

    return {
        "sesskey": field("sesskey"),
        "content_itemid": field("content[itemid]"),
        "attachment_itemid": field("attachment"),
    }


def post_new_thread(
    session: PlatoSession, board_id: int, subject: str, content_text: str
) -> None:
    """POST a new top-level question to a Q&A board.

    Raises requests.HTTPError on a non-2xx response. Does not (yet) parse
    the response to confirm the post actually saved -- see issue follow-up
    in docs/ubboard_structure.md; the caller (issue #27's post_qna_question)
    is responsible for verifying via a subsequent list_qna call if needed.
    """
    tokens = _fetch_write_form_tokens(session, board_id)

    default_rate_limiter.check(session.session_key)
    resp = session.requests_session.post(
        f"{BASE_URL}/mod/ubboard/write.php",
        params={"id": board_id},
        data={
            "id": board_id,
            "coursemostype": "insert",
            "bwid": "",
            "rnum": "",
            "sesskey": tokens["sesskey"],
            "_qf__mod_ubboard_write_form": 1,
            "mform_isexpanded_id_general-ubboard": 1,
            "subject": subject,
            "secret": DEFAULT_SECRET,
            "content[text]": content_text,
            "content[format]": 1,
            "content[itemid]": tokens["content_itemid"],
            "attachment": tokens["attachment_itemid"],
            "submitbutton": "Save",
        },
        timeout=15,
    )
    resp.raise_for_status()
