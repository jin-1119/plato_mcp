"""Unit tests for ubboard/writer.py -- mocked HTTP, no real POST ever made here.

An actual write against the live PLATO server is a real, visible, hard-to-
undo action (a post appears on a real course board), so it is NOT exercised
automatically -- see the PR/issue notes for how that was verified instead.
"""

import pytest

from plato_mcp.errors import ScrapeError
from plato_mcp.ubboard.writer import _fetch_write_form_tokens, post_new_thread

WRITE_FORM_HTML = """
<form id="mformubboard" action="write.php" method="post">
  <input name="sesskey" value="SESSKEY123" />
  <textarea name="content[text]"></textarea>
  <input name="content[itemid]" value="111222333" />
  <input name="attachment" value="444555666" />
</form>
"""


@pytest.fixture
def mock_session(mocker):
    session = mocker.Mock()
    session.requests_session = mocker.Mock()
    return session


def test_fetch_write_form_tokens_extracts_all_fields(mock_session, mocker):
    resp = mocker.Mock(text=WRITE_FORM_HTML)
    resp.raise_for_status.return_value = None
    mock_session.requests_session.get.return_value = resp

    tokens = _fetch_write_form_tokens(mock_session, board_id=37083)

    assert tokens == {
        "sesskey": "SESSKEY123",
        "content_itemid": "111222333",
        "attachment_itemid": "444555666",
    }
    call_args = mock_session.requests_session.get.call_args
    assert call_args.kwargs["params"] == {"id": 37083}


def test_fetch_write_form_tokens_missing_form_raises_scrape_error(mock_session, mocker):
    resp = mocker.Mock(text="<html>no form here</html>")
    resp.raise_for_status.return_value = None
    mock_session.requests_session.get.return_value = resp

    with pytest.raises(ScrapeError):
        _fetch_write_form_tokens(mock_session, board_id=37083)


def test_fetch_write_form_tokens_missing_field_raises_scrape_error(mock_session, mocker):
    resp = mocker.Mock(
        text='<form id="mformubboard"><input name="sesskey" value="X" /></form>'
    )
    resp.raise_for_status.return_value = None
    mock_session.requests_session.get.return_value = resp

    with pytest.raises(ScrapeError):
        _fetch_write_form_tokens(mock_session, board_id=37083)


def test_post_new_thread_sends_correct_payload(mock_session, mocker):
    get_resp = mocker.Mock(text=WRITE_FORM_HTML)
    get_resp.raise_for_status.return_value = None
    post_resp = mocker.Mock()
    post_resp.raise_for_status.return_value = None
    mock_session.requests_session.get.return_value = get_resp
    mock_session.requests_session.post.return_value = post_resp

    post_new_thread(mock_session, board_id=37083, subject="My question", content_text="Body text")

    post_call = mock_session.requests_session.post.call_args
    assert post_call.kwargs["params"] == {"id": 37083}
    data = post_call.kwargs["data"]
    assert data["sesskey"] == "SESSKEY123"
    assert data["subject"] == "My question"
    assert data["content[text]"] == "Body text"
    assert data["content[itemid]"] == "111222333"
    assert data["attachment"] == "444555666"
    assert data["coursemostype"] == "insert"
    assert data["bwid"] == ""  # empty -- new post, not a reply
    assert data["secret"] == 1  # defaults to the same "secret" default as the live form


def test_post_new_thread_fetches_fresh_tokens_each_call(mock_session, mocker):
    """content[itemid]/attachment are per-page-load random ids -- must never
    be cached or reused across separate post_new_thread calls."""
    responses = [
        mocker.Mock(text=WRITE_FORM_HTML.replace("111222333", "AAA")),
        mocker.Mock(text=WRITE_FORM_HTML.replace("111222333", "BBB")),
    ]
    for r in responses:
        r.raise_for_status.return_value = None
    mock_session.requests_session.get.side_effect = responses
    post_resp = mocker.Mock()
    post_resp.raise_for_status.return_value = None
    mock_session.requests_session.post.return_value = post_resp

    post_new_thread(mock_session, board_id=1, subject="Q1", content_text="C1")
    post_new_thread(mock_session, board_id=1, subject="Q2", content_text="C2")

    post_calls = mock_session.requests_session.post.call_args_list
    first_itemid = post_calls[0].kwargs["data"]["content[itemid]"]
    second_itemid = post_calls[1].kwargs["data"]["content[itemid]"]
    assert first_itemid == "AAA"
    assert second_itemid == "BBB"
    assert mock_session.requests_session.get.call_count == 2
