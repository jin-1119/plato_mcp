import pytest

from plato_mcp.auth import SessionManager
from plato_mcp.errors import MoodleAPIError
from plato_mcp.moodle_client import MoodleClient, flatten_params


@pytest.fixture
def manager_with_session(mocker):
    manager = SessionManager()
    mocker.patch.object(manager, "_fetch_token", return_value="tok-initial")
    manager.get_or_login("session-1", "u1", "p1")
    return manager


@pytest.fixture
def client(manager_with_session):
    return MoodleClient(manager_with_session, "session-1", "u1", "p1")


def test_flatten_params_scalar_passthrough():
    assert flatten_params({"courseid": 5}) == {"courseid": 5}


def test_flatten_params_list_expands_to_brackets():
    assert flatten_params({"courseids": [10, 20]}) == {"courseids[0]": 10, "courseids[1]": 20}


def test_flatten_params_list_of_dicts():
    result = flatten_params({"options": [{"name": "a", "value": 1}]})
    assert result == {"options[0][name]": "a", "options[0][value]": 1}


def test_call_success_returns_result(client, mocker):
    mock_resp = mocker.Mock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"sitename": "PLATO"}
    mocker.patch("plato_mcp.moodle_client.requests.post", return_value=mock_resp)

    result = client.call("core_webservice_get_site_info")
    assert result == {"sitename": "PLATO"}


def test_call_generic_error_raises_moodle_api_error(client, mocker):
    mock_resp = mocker.Mock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "exception": "moodle_exception",
        "errorcode": "nopermissiontoviewgrades",
        "message": "No permission",
    }
    mocker.patch("plato_mcp.moodle_client.requests.post", return_value=mock_resp)

    with pytest.raises(MoodleAPIError) as excinfo:
        client.call("gradereport_user_get_grade_items", courseid=1)
    assert excinfo.value.errorcode == "nopermissiontoviewgrades"


def test_call_invalidtoken_retries_once_then_succeeds(client, manager_with_session, mocker):
    fetch = mocker.patch.object(manager_with_session, "_fetch_token", return_value="tok-refreshed")

    responses = [
        mocker.Mock(json=mocker.Mock(return_value={"errorcode": "invalidtoken"})),
        mocker.Mock(json=mocker.Mock(return_value={"sitename": "PLATO"})),
    ]
    for r in responses:
        r.raise_for_status.return_value = None
    mock_post = mocker.patch("plato_mcp.moodle_client.requests.post", side_effect=responses)

    result = client.call("core_webservice_get_site_info")

    assert result == {"sitename": "PLATO"}
    assert mock_post.call_count == 2
    assert fetch.call_count == 1  # exactly one refresh, not stuck retrying


def test_call_invalidtoken_twice_raises_after_single_retry(client, manager_with_session, mocker):
    mocker.patch.object(manager_with_session, "_fetch_token", return_value="tok-still-bad")

    mock_resp = mocker.Mock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"errorcode": "invalidtoken"}
    mock_post = mocker.patch("plato_mcp.moodle_client.requests.post", return_value=mock_resp)

    with pytest.raises(MoodleAPIError) as excinfo:
        client.call("core_webservice_get_site_info")

    assert excinfo.value.errorcode == "invalidtoken"
    assert mock_post.call_count == 2  # tried once, retried once, then gave up


def test_call_passes_wstoken_and_wsfunction_in_post_body(client, mocker):
    mock_resp = mocker.Mock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"ok": True}
    mock_post = mocker.patch("plato_mcp.moodle_client.requests.post", return_value=mock_resp)

    client.call("core_course_get_contents", courseid=6253)

    _, kwargs = mock_post.call_args
    assert kwargs["data"]["wstoken"] == "tok-initial"
    assert kwargs["data"]["wsfunction"] == "core_course_get_contents"
    assert kwargs["data"]["moodlewsrestformat"] == "json"
    assert kwargs["data"]["courseid"] == 6253
