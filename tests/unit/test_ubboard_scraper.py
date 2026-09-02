"""Unit tests for ubboard/scraper.py -- mocked MoodleClient + PlatoSession,
no live network calls."""

import json

import pytest

from plato_mcp.errors import ScrapeError
from plato_mcp.ubboard.scraper import (
    find_board_id,
    get_notice_detail_for,
    get_qna_detail_for,
    list_notices_for,
    list_qna_for,
)

COURSE_CONTENTS = [
    {
        "id": 1,
        "name": "Course overview",
        "modules": [
            {
                "id": 37082,
                "modname": "ubboard",
                "name": "Notices",
                "customdata": json.dumps({"type": "notice", "basic": "1"}),
            },
            {
                "id": 37083,
                "modname": "ubboard",
                "name": "Q&A",
                "customdata": json.dumps({"type": "qna", "basic": "2"}),
            },
            {
                "id": 37090,
                "modname": "resource",
                "name": "Syllabus",
            },
        ],
    }
]


@pytest.fixture
def mock_client(mocker):
    client = mocker.Mock()
    client.call.return_value = COURSE_CONTENTS
    return client


@pytest.fixture
def mock_ubboard_session(mocker):
    session = mocker.Mock()
    session.requests_session = mocker.Mock()
    return session


def test_find_board_id_notice(mock_client):
    assert find_board_id(mock_client, course_id=6253, board_type="notice") == 37082


def test_find_board_id_qna(mock_client):
    assert find_board_id(mock_client, course_id=6253, board_type="qna") == 37083


def test_find_board_id_not_found_raises_scrape_error(mock_client):
    mock_client.call.return_value = [{"id": 1, "name": "s", "modules": []}]
    with pytest.raises(ScrapeError):
        find_board_id(mock_client, course_id=6253, board_type="notice")


def test_find_board_id_ignores_malformed_customdata(mock_client):
    mock_client.call.return_value = [
        {
            "id": 1,
            "name": "s",
            "modules": [{"id": 1, "modname": "ubboard", "name": "x", "customdata": "not json"}],
        }
    ]
    with pytest.raises(ScrapeError):
        find_board_id(mock_client, course_id=6253, board_type="notice")


def test_list_notices_for_resolves_board_and_parses(mock_client, mock_ubboard_session, mocker):
    list_html = """
    <div class="grid-table">
      <div class="grid-row grid-row-header"></div>
      <div class="grid-row grid-row-notice">
        <div class="grid-cell-subject">
          <a href="article.php?id=37082&bwid=14938"><div class="text-truncate text">Hi</div></a>
        </div>
      </div>
    </div>
    """
    resp = mocker.Mock(text=list_html)
    resp.raise_for_status.return_value = None
    mock_ubboard_session.requests_session.get.return_value = resp

    result = list_notices_for(mock_client, mock_ubboard_session, course_id=6253)

    assert len(result) == 1
    assert result[0].post_id == 14938
    assert result[0].board_id == 37082

    # Fetched the notice board (37082), not the qna board (37083)
    call_args = mock_ubboard_session.requests_session.get.call_args
    assert call_args.kwargs["params"]["id"] == 37082
    assert call_args.kwargs["params"]["listsize"] == 0


def test_get_notice_detail_for_resolves_board_and_parses(mock_client, mock_ubboard_session, mocker):
    detail_html = """
    <h3 class="article-title">Notice about course operation</h3>
    <div class="subject-box-description">
      <div class="csms-user-picture"><div class="text-truncate">Jin-Woo Kim</div></div>
      <div class="subject-description-date">2026-08-28 14:06:15</div>
    </div>
    <div class="article-content"><div class="text_to_html"><p>Hello.</p></div></div>
    """
    resp = mocker.Mock(text=detail_html)
    resp.raise_for_status.return_value = None
    mock_ubboard_session.requests_session.get.return_value = resp

    result = get_notice_detail_for(mock_client, mock_ubboard_session, course_id=6253, post_id=14938)

    assert result.title == "Notice about course operation"
    assert result.writer == "Jin-Woo Kim"
    assert "Hello." in result.content_html

    call_args = mock_ubboard_session.requests_session.get.call_args
    assert call_args.kwargs["params"] == {"id": 37082, "bwid": 14938}


def test_list_qna_for_uses_qna_board_not_notice_board(mock_client, mock_ubboard_session, mocker):
    """Empty board case -- the only kind of Q&A board ever actually observed
    live (see docs/ubboard_structure.md section 5)."""
    empty_html = """
    <div class="grid-table">
      <div class="grid-row grid-row-header"></div>
      <div class="grid-row grid-row-nodata"></div>
    </div>
    """
    resp = mocker.Mock(text=empty_html)
    resp.raise_for_status.return_value = None
    mock_ubboard_session.requests_session.get.return_value = resp

    result = list_qna_for(mock_client, mock_ubboard_session, course_id=6253)

    assert result == []
    call_args = mock_ubboard_session.requests_session.get.call_args
    assert call_args.kwargs["params"]["id"] == 37083  # the qna board, not 37082 (notice)


def test_get_qna_detail_for_uses_qna_board_and_parses_like_notice(
    mock_client, mock_ubboard_session, mocker
):
    """No real Q&A thread has ever been observed, so this can only be
    verified against the same detail-page structure as Notices (same
    ubboard theme). Replies are explicitly not parsed -- see get_qna_detail_for's
    docstring."""
    detail_html = """
    <h3 class="article-title">Question about grading</h3>
    <div class="subject-box-description">
      <div class="csms-user-picture"><div class="text-truncate">A Student</div></div>
      <div class="subject-description-date">2026-09-01 10:00:00</div>
    </div>
    <div class="article-content"><div class="text_to_html"><p>How is this graded?</p></div></div>
    """
    resp = mocker.Mock(text=detail_html)
    resp.raise_for_status.return_value = None
    mock_ubboard_session.requests_session.get.return_value = resp

    result = get_qna_detail_for(mock_client, mock_ubboard_session, course_id=6253, post_id=1)

    assert result.title == "Question about grading"
    assert result.writer == "A Student"
    assert "How is this graded?" in result.content_html

    call_args = mock_ubboard_session.requests_session.get.call_args
    assert call_args.kwargs["params"] == {"id": 37083, "bwid": 1}
