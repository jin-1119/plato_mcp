"""Unit tests for files.py -- mocked MoodleClient + requests, no live network."""

import pytest

from plato_mcp.errors import PlatoMCPError
from plato_mcp.files import DownloadRejectedError, download_course_file_for


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
