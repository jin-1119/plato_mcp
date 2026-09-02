"""Unit tests for tools/notices_qna.py's post_qna_question_for -- mocked
MoodleClient + PlatoSession, no live network calls."""

import json

import pytest

from plato_mcp.tools.notices_qna import post_qna_question_for

COURSE_CONTENTS = [
    {
        "id": 1,
        "name": "Course overview",
        "modules": [
            {
                "id": 37083,
                "modname": "ubboard",
                "name": "Q&A",
                "customdata": json.dumps({"type": "qna", "basic": "2"}),
            }
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


def test_post_qna_question_for_dry_run_does_not_post(mock_client, mock_ubboard_session):
    result = post_qna_question_for(
        mock_client, mock_ubboard_session, course_id=6253, subject="Q1", content_text="body"
    )

    assert result.dry_run is True
    assert result.executed is False
    assert result.preview["subject"] == "Q1"
    assert result.preview["board_id"] == 37083
    mock_ubboard_session.requests_session.get.assert_not_called()
    mock_ubboard_session.requests_session.post.assert_not_called()


def test_post_qna_question_for_real_run_posts(mock_client, mock_ubboard_session, mocker):
    write_form_html = """
    <form id="mformubboard">
      <input name="sesskey" value="SK" />
      <textarea name="content[text]"></textarea>
      <input name="content[itemid]" value="111" />
      <input name="attachment" value="222" />
    </form>
    """
    get_resp = mocker.Mock(text=write_form_html)
    get_resp.raise_for_status.return_value = None
    post_resp = mocker.Mock()
    post_resp.raise_for_status.return_value = None
    mock_ubboard_session.requests_session.get.return_value = get_resp
    mock_ubboard_session.requests_session.post.return_value = post_resp

    # dry_run=False now requires a matching preview first (issue #37).
    post_qna_question_for(
        mock_client, mock_ubboard_session, course_id=6253, subject="Q1", content_text="body"
    )
    result = post_qna_question_for(
        mock_client,
        mock_ubboard_session,
        course_id=6253,
        subject="Q1",
        content_text="body",
        dry_run=False,
    )

    assert result.dry_run is False
    assert result.executed is True

    post_call = mock_ubboard_session.requests_session.post.call_args
    assert post_call.kwargs["params"] == {"id": 37083}
    assert post_call.kwargs["data"]["subject"] == "Q1"
    assert post_call.kwargs["data"]["content[text]"] == "body"
