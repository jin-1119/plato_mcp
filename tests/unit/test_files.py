"""Unit tests for files.py -- mocked MoodleClient + requests, no live network."""

import base64

import pytest

from plato_mcp.errors import PlatoMCPError
from plato_mcp.files import (
    DownloadContentResult,
    DownloadLinkResult,
    DownloadRejectedError,
    build_course_file_download_url,
    download_course_file_for,
    fetch_course_file_content_or_link_for,
)


@pytest.fixture
def mock_client(mocker):
    client = mocker.Mock()
    client.get_wstoken.return_value = "TOK123"
    return client


def test_download_rejects_disallowed_extension(mock_client, tmp_path):
    with pytest.raises(DownloadRejectedError):
        download_course_file_for(
            mock_client, "https://x/y/malware.exe", str(tmp_path / "out.exe")
        )


def test_download_rejects_before_touching_network(mock_client, tmp_path, mocker):
    get = mocker.patch("plato_mcp.files.requests.get")
    with pytest.raises(DownloadRejectedError):
        download_course_file_for(mock_client, "https://x/y/bad.sh", str(tmp_path / "out.sh"))
    get.assert_not_called()


def test_download_appends_token_to_url(mock_client, tmp_path, mocker):
    resp = mocker.MagicMock()
    resp.headers = {"content-length": "5", "content-type": "application/pdf"}
    resp.iter_content.return_value = [b"hello"]
    resp.raise_for_status.return_value = None
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    mock_get = mocker.patch("plato_mcp.files.requests.get", return_value=resp)

    dest = tmp_path / "out.pdf"
    result = download_course_file_for(mock_client, "https://x/y/file.pdf", str(dest))

    called_url = mock_get.call_args.args[0]
    assert called_url == "https://x/y/file.pdf?token=TOK123"
    assert result.size_bytes == 5
    assert result.mimetype == "application/pdf"
    assert dest.read_bytes() == b"hello"


def test_download_url_with_existing_query_uses_ampersand(mock_client, tmp_path, mocker):
    resp = mocker.MagicMock()
    resp.headers = {}
    resp.iter_content.return_value = [b"x"]
    resp.raise_for_status.return_value = None
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    mock_get = mocker.patch("plato_mcp.files.requests.get", return_value=resp)

    download_course_file_for(
        mock_client, "https://x/y/file.pdf?forcedownload=1", str(tmp_path / "o.pdf")
    )

    called_url = mock_get.call_args.args[0]
    assert called_url == "https://x/y/file.pdf?forcedownload=1&token=TOK123"


def test_download_rejects_via_content_length_header_before_streaming(mock_client, tmp_path, mocker):
    resp = mocker.MagicMock()
    resp.headers = {"content-length": str(50 * 1024 * 1024)}  # 50MB
    resp.raise_for_status.return_value = None
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    mocker.patch("plato_mcp.files.requests.get", return_value=resp)

    with pytest.raises(DownloadRejectedError):
        download_course_file_for(
            mock_client, "https://x/y/big.pdf", str(tmp_path / "big.pdf"), max_download_mb=1
        )
    resp.iter_content.assert_not_called()  # rejected before streaming any bytes


def test_download_rejects_mid_stream_when_no_content_length(mock_client, tmp_path, mocker):
    # Server doesn't report content-length, but the actual bytes exceed the limit.
    big_chunk = b"x" * (2 * 1024 * 1024)  # 2MB chunks
    resp = mocker.MagicMock()
    resp.headers = {}
    resp.iter_content.return_value = [big_chunk, big_chunk]  # 4MB total
    resp.raise_for_status.return_value = None
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    mocker.patch("plato_mcp.files.requests.get", return_value=resp)

    dest = tmp_path / "big.pdf"
    with pytest.raises(DownloadRejectedError):
        download_course_file_for(mock_client, "https://x/y/big.pdf", str(dest), max_download_mb=1)

    assert not dest.exists()  # partial file cleaned up


def test_download_rejected_error_is_plato_mcp_error():
    assert issubclass(DownloadRejectedError, PlatoMCPError)


# -- build_course_file_download_url (issue #55: remote-transport delivery) --
# No save_path parameter exists on this function at all, so it structurally
# cannot touch disk -- that's the regression guard, not an assertion on mocks.


def test_build_download_url_rejects_disallowed_extension(mock_client):
    with pytest.raises(DownloadRejectedError):
        build_course_file_download_url(mock_client, "https://x/y/malware.exe")


def test_build_download_url_rejects_before_touching_network(mock_client, mocker):
    get = mocker.patch("plato_mcp.files.requests.get")
    with pytest.raises(DownloadRejectedError):
        build_course_file_download_url(mock_client, "https://x/y/bad.sh")
    get.assert_not_called()


def test_build_download_url_appends_token_with_no_existing_query(mock_client):
    result = build_course_file_download_url(mock_client, "https://x/y/file.pdf")
    assert isinstance(result, DownloadLinkResult)
    assert result.url == "https://x/y/file.pdf?token=TOK123"
    assert result.filename == "file.pdf"
    assert result.warning  # non-empty, response-level (not just docstring) warning


def test_build_download_url_appends_token_with_existing_query(mock_client):
    result = build_course_file_download_url(
        mock_client, "https://x/y/file.pdf?forcedownload=1"
    )
    assert result.url == "https://x/y/file.pdf?forcedownload=1&token=TOK123"


def test_build_download_url_never_touches_network(mock_client, mocker):
    get = mocker.patch("plato_mcp.files.requests.get")
    build_course_file_download_url(mock_client, "https://x/y/file.pdf")
    get.assert_not_called()


def test_download_course_file_for_reuses_build_download_url(mock_client, tmp_path, mocker):
    # download_course_file_for (the stdio path) shares the same extension
    # check + URL-building logic instead of duplicating it.
    resp = mocker.MagicMock()
    resp.headers = {"content-length": "5", "content-type": "application/pdf"}
    resp.iter_content.return_value = [b"hello"]
    resp.raise_for_status.return_value = None
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    mock_get = mocker.patch("plato_mcp.files.requests.get", return_value=resp)

    download_course_file_for(mock_client, "https://x/y/file.pdf", str(tmp_path / "o.pdf"))

    called_url = mock_get.call_args.args[0]
    assert called_url == "https://x/y/file.pdf?token=TOK123"


# -- fetch_course_file_content_or_link_for (issue #55 redesign: inline
# base64 for small files, prompted by observing a real Claude.ai session
# decode a Google Drive MCP tool's inline base64 response and present it as
# an actual downloadable file -- see docs/smithery_deployment_model.md) --


def _mock_resp(mocker, headers, chunks):
    resp = mocker.MagicMock()
    resp.headers = headers
    resp.iter_content.return_value = chunks
    resp.raise_for_status.return_value = None
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


def test_fetch_content_or_link_rejects_disallowed_extension(mock_client):
    with pytest.raises(DownloadRejectedError):
        fetch_course_file_content_or_link_for(mock_client, "https://x/y/malware.exe")


def test_fetch_content_or_link_small_file_returns_inline_base64(mock_client, mocker):
    resp = _mock_resp(
        mocker, {"content-length": "5", "content-type": "application/pdf"}, [b"hello"]
    )
    mocker.patch("plato_mcp.files.requests.get", return_value=resp)

    result = fetch_course_file_content_or_link_for(mock_client, "https://x/y/file.pdf")

    assert isinstance(result, DownloadContentResult)
    assert result.filename == "file.pdf"
    assert result.size_bytes == 5
    assert result.mimetype == "application/pdf"
    assert base64.b64decode(result.content_base64) == b"hello"


def test_fetch_content_or_link_large_content_length_falls_back_to_link(mock_client, mocker):
    big = 10 * 1024 * 1024  # 10MB, over the 5MB inline threshold
    resp = _mock_resp(mocker, {"content-length": str(big)}, [])
    mocker.patch("plato_mcp.files.requests.get", return_value=resp)

    result = fetch_course_file_content_or_link_for(mock_client, "https://x/y/big.pdf")

    assert isinstance(result, DownloadLinkResult)
    assert result.url == "https://x/y/big.pdf?token=TOK123"
    assert result.warning
    resp.iter_content.assert_not_called()  # bailed before streaming any bytes


def test_fetch_content_or_link_large_body_with_no_content_length_falls_back(mock_client, mocker):
    # Server doesn't report content-length, but the body turns out too big.
    big_chunk = b"x" * (3 * 1024 * 1024)  # 3MB chunks, 2 of them exceeds the 5MB threshold
    resp = _mock_resp(mocker, {}, [big_chunk, big_chunk])
    mocker.patch("plato_mcp.files.requests.get", return_value=resp)

    result = fetch_course_file_content_or_link_for(mock_client, "https://x/y/big.pdf")

    assert isinstance(result, DownloadLinkResult)


def test_fetch_content_or_link_never_touches_disk(mock_client, mocker):
    # Structural guard: this function takes no save_path and should never
    # open a file on disk, for either the inline or the fallback outcome.
    resp = _mock_resp(
        mocker, {"content-length": "5", "content-type": "application/pdf"}, [b"hello"]
    )
    mocker.patch("plato_mcp.files.requests.get", return_value=resp)
    open_mock = mocker.patch("builtins.open")

    fetch_course_file_content_or_link_for(mock_client, "https://x/y/file.pdf")

    open_mock.assert_not_called()


def test_fetch_content_or_link_respects_custom_max_inline_mb(mock_client, mocker):
    resp = _mock_resp(mocker, {"content-length": str(2 * 1024 * 1024)}, [])
    mocker.patch("plato_mcp.files.requests.get", return_value=resp)

    # 2MB file, but max_inline_mb=1 -- should fall back even though it'd
    # normally fit under the 5MB default.
    result = fetch_course_file_content_or_link_for(
        mock_client, "https://x/y/file.pdf", max_inline_mb=1
    )

    assert isinstance(result, DownloadLinkResult)
