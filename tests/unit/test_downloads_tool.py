"""Unit tests for tools/downloads.py's transport-branching logic (issue #55).

Tests download_course_file_tool_for directly against a mocked MoodleClient
and a plain `headers` value (None for stdio, a dict for HTTP) -- no live MCP
Context needed, same pattern as test_tools.py's other `*_for` tests.
"""

import pytest

from plato_mcp.errors import PlatoMCPError
from plato_mcp.files import DownloadLinkResult, DownloadResult
from plato_mcp.tools.downloads import download_course_file_tool_for


@pytest.fixture
def mock_client(mocker):
    client = mocker.Mock()
    client.get_wstoken.return_value = "TOK123"
    return client


def test_stdio_headers_none_saves_to_disk(mock_client, tmp_path, mocker):
    resp = mocker.MagicMock()
    resp.headers = {"content-length": "5", "content-type": "application/pdf"}
    resp.iter_content.return_value = [b"hello"]
    resp.raise_for_status.return_value = None
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    mocker.patch("plato_mcp.files.requests.get", return_value=resp)

    dest = tmp_path / "out.pdf"
    result = download_course_file_tool_for(
        mock_client, None, "https://x/y/file.pdf", str(dest)
    )

    assert isinstance(result, DownloadResult)
    assert dest.read_bytes() == b"hello"


def test_stdio_without_save_path_raises(mock_client):
    with pytest.raises(PlatoMCPError):
        download_course_file_tool_for(mock_client, None, "https://x/y/file.pdf", None)


def test_http_headers_present_returns_url_not_disk_write(mock_client, mocker):
    get = mocker.patch("plato_mcp.files.requests.get")

    result = download_course_file_tool_for(
        mock_client, {"pnu_id": "u", "pnu_password": "p"}, "https://x/y/file.pdf", None
    )

    assert isinstance(result, DownloadLinkResult)
    assert result.url == "https://x/y/file.pdf?token=TOK123"
    assert result.warning
    get.assert_not_called()  # never fetched server-side, no disk touched either


def test_http_with_save_path_raises_clear_error(mock_client):
    with pytest.raises(PlatoMCPError):
        download_course_file_tool_for(
            mock_client,
            {"pnu_id": "u", "pnu_password": "p"},
            "https://x/y/file.pdf",
            "/tmp/out.pdf",
        )


def test_http_empty_headers_mapping_still_counts_as_http(mock_client, mocker):
    # An empty dict is still "not None" -- e.g. a streamable-http request
    # with no config headers should still take the HTTP branch, not fall
    # back to treating it as stdio.
    get = mocker.patch("plato_mcp.files.requests.get")

    result = download_course_file_tool_for(mock_client, {}, "https://x/y/file.pdf", None)

    assert isinstance(result, DownloadLinkResult)
    get.assert_not_called()
