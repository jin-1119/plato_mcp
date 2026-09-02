"""Pure HTML -> model parsing for ubboard pages.

No HTTP here on purpose -- these functions take an HTML string and return
parsed models (or raise ScrapeError), so they're unit-testable against
saved fixtures with no network access. HTTP fetching lives in scraper.py
(issue #22/#23).

Selectors are documented in docs/ubboard_structure.md (issue #19 findings).
Q&A reply/thread nesting is NOT handled here -- no real Q&A thread has ever
been observed, so there is nothing verified to parse yet (see the doc's
"Not verified" note). list/detail parsing below works for both notice and
qna boards, since they share the same ubboard theme markup.
"""

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup, Tag

from plato_mcp.errors import ScrapeError
from plato_mcp.ubboard.models import UbboardPostDetail, UbboardPostSummary

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.strptime(text.strip(), DATE_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        return None


def _parse_post_id_from_href(href: str) -> int:
    query = parse_qs(urlparse(href).query)
    bwid = query.get("bwid")
    if not bwid:
        raise ScrapeError(f"list row link has no bwid query param: {href!r}")
    return int(bwid[0])


def parse_list_page(html: str, board_id: int) -> list[UbboardPostSummary]:
    """Parse a `view.php?id=<board_id>` list page into post summaries.

    An empty board (grid-row-nodata) returns an empty list, not an error.
    """
    soup = BeautifulSoup(html, "html.parser")
    grid = soup.select_one(".grid-table")
    if grid is None:
        raise ScrapeError("ubboard list page missing .grid-table -- page structure changed?")

    skip_classes = {"grid-row-header", "grid-row-nodata"}
    rows = [
        row for row in grid.select(".grid-row") if skip_classes.isdisjoint(row.get("class", []))
    ]

    summaries = []
    for row in rows:
        summaries.append(_parse_list_row(row, board_id))
    return summaries


def _parse_list_row(row: Tag, board_id: int) -> UbboardPostSummary:
    try:
        link = row.select_one(".grid-cell-subject a[href]")
        if link is None:
            raise ScrapeError("list row missing subject link")
        post_id = _parse_post_id_from_href(link["href"])

        title_el = link.select_one(".text-truncate.text")
        title = title_el.get_text(strip=True) if title_el else link.get_text(strip=True)

        writer_el = row.select_one(".grid-cell-writer .text-truncate")
        writer = writer_el.get_text(strip=True) if writer_el else None

        date_el = row.select_one(".grid-cell-date span[title]")
        posted_at = _parse_date(date_el["title"]) if date_el else None

        view_el = row.select_one(".grid-cell-viewcount .count")
        view_text = view_el.get_text(strip=True) if view_el else ""
        view_count = int(view_text) if view_text.isdigit() else None

        return UbboardPostSummary(
            board_id=board_id,
            post_id=post_id,
            title=title,
            writer=writer,
            posted_at=posted_at,
            view_count=view_count,
        )
    except ScrapeError:
        raise
    except (AttributeError, KeyError, ValueError, TypeError) as e:
        raise ScrapeError(f"failed to parse ubboard list row: {e}") from e


def parse_detail_page(html: str, board_id: int, post_id: int) -> UbboardPostDetail:
    """Parse an `article.php?id=<board_id>&bwid=<post_id>` detail page."""
    soup = BeautifulSoup(html, "html.parser")

    try:
        title_el = soup.select_one("h3.article-title")
        if title_el is None:
            raise ScrapeError("detail page missing h3.article-title -- page structure changed?")
        title = title_el.get_text(strip=True)

        writer_el = soup.select_one(".subject-box-description .csms-user-picture .text-truncate")
        writer = writer_el.get_text(strip=True) if writer_el else None

        date_el = soup.select_one(".subject-description-date")
        posted_at = _parse_date(date_el.get_text(strip=True)) if date_el else None

        view_el = soup.select_one(".subject-description-viewcount")
        view_count = None
        if view_el:
            digits = "".join(c for c in view_el.get_text(strip=True) if c.isdigit())
            view_count = int(digits) if digits else None

        content_el = soup.select_one(".article-content .text_to_html")
        content_html = content_el.decode_contents().strip() if content_el else ""

        return UbboardPostDetail(
            board_id=board_id,
            post_id=post_id,
            title=title,
            writer=writer,
            posted_at=posted_at,
            view_count=view_count,
            content_html=content_html,
        )
    except ScrapeError:
        raise
    except (AttributeError, KeyError, ValueError, TypeError) as e:
        raise ScrapeError(f"failed to parse ubboard detail page: {e}") from e
