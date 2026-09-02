"""Unit tests for ubboard/parser.py, run against real (scrubbed) fixtures
captured in issue #19 -- no live network calls.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from plato_mcp.errors import ScrapeError
from plato_mcp.ubboard.parser import parse_detail_page, parse_list_page

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ubboard"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_list_page_real_notice_with_post():
    result = parse_list_page(fixture("notice_list.html"), board_id=37082)

    assert len(result) == 1
    post = result[0]
    assert post.board_id == 37082
    assert post.post_id == 14938
    assert post.title == "Notice about course operation"
    assert post.writer == "Jin-Woo Kim"
    assert post.posted_at == datetime(2026, 8, 28, 14, 6, 15, tzinfo=UTC)
    assert post.view_count == 37


def test_parse_list_page_empty_board_returns_empty_list():
    result = parse_list_page(fixture("qna_list_empty.html"), board_id=37083)
    assert result == []


def test_parse_list_page_missing_grid_raises_scrape_error():
    with pytest.raises(ScrapeError):
        parse_list_page("<html><body>not a ubboard page</body></html>", board_id=1)


def test_parse_detail_page_real_notice():
    result = parse_detail_page(fixture("notice_detail.html"), board_id=37082, post_id=14938)

    assert result.title == "Notice about course operation"
    assert result.writer == "Jin-Woo Kim"
    assert result.posted_at == datetime(2026, 8, 28, 14, 6, 15, tzinfo=UTC)
    assert result.view_count == 37
    assert "Hello everyone." in result.content_html
    assert "<p>" in result.content_html  # real markup preserved, not just get_text()'d


def test_parse_detail_page_missing_title_raises_scrape_error():
    with pytest.raises(ScrapeError):
        parse_detail_page("<html><body>no article here</body></html>", board_id=1, post_id=1)


def test_parse_list_page_tolerates_missing_optional_fields():
    """A row with no writer/date/viewcount markup shouldn't crash -- those
    fields should just come back None, only a missing subject link is fatal."""
    html = """
    <div class="grid-table">
      <div class="grid-row grid-row-header"><div class="grid-cell-subject">Subject</div></div>
      <div class="grid-row grid-row-notice">
        <div class="grid-cell-subject">
          <a href="article.php?id=1&bwid=999"><div class="text-truncate text">Bare post</div></a>
        </div>
      </div>
    </div>
    """
    result = parse_list_page(html, board_id=1)
    assert len(result) == 1
    assert result[0].post_id == 999
    assert result[0].title == "Bare post"
    assert result[0].writer is None
    assert result[0].posted_at is None
    assert result[0].view_count is None


def test_parse_list_page_row_missing_link_raises_scrape_error():
    html = """
    <div class="grid-table">
      <div class="grid-row grid-row-notice">
        <div class="grid-cell-subject">no link here</div>
      </div>
    </div>
    """
    with pytest.raises(ScrapeError):
        parse_list_page(html, board_id=1)
