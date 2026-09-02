"""download_course_file logic (issue #28).

fileurl values from get_course_contents (models.FileEntry) become an
authenticated download by appending ?token={wstoken} -- confirmed during
initial research: a real course PDF downloaded successfully this exact
way, no scraping needed (see PLATO_MCP_사전조사.md).
"""

from pathlib import Path
from urllib.parse import urlparse

import requests
from pydantic import BaseModel

from plato_mcp.errors import PlatoMCPError
from plato_mcp.moodle_client import MoodleClient

# Deliberately conservative: course-material types only, no executables/scripts.
ALLOWED_EXTENSIONS = {
    ".pdf", ".ppt", ".pptx", ".doc", ".docx", ".xls", ".xlsx",
    ".hwp", ".zip", ".txt", ".png", ".jpg", ".jpeg", ".gif",
}


class DownloadRejectedError(PlatoMCPError):
    """A download was refused -- disallowed extension, or over max_download_mb."""


class DownloadResult(BaseModel):
    path: str
    size_bytes: int
    mimetype: str | None = None


def _extension_of(file_url: str) -> str:
    return Path(urlparse(file_url).path).suffix.lower()


def download_course_file_for(
    client: MoodleClient, file_url: str, save_path: str, max_download_mb: int = 20
) -> DownloadResult:
    ext = _extension_of(file_url)
    if ext not in ALLOWED_EXTENSIONS:
        raise DownloadRejectedError(f"disallowed file extension: {ext!r}")

    token = client.get_wstoken()
    separator = "&" if "?" in file_url else "?"
    download_url = f"{file_url}{separator}token={token}"

    max_bytes = max_download_mb * 1024 * 1024
    dest = Path(save_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    # This one has to stay a GET with the token in the URL -- that's how
    # Moodle's pluginfile.php authenticates a direct file download, there's
    # no POST-body alternative. So unlike auth.py/moodle_client.py (which
    # avoid this by switching to POST), we can't stop the token from being
    # in the URL -- only catch and sanitize what `requests` does with it on
    # failure, since HTTPError/RequestException otherwise embed the full
    # URL (token included) verbatim in their message.
    try:
        resp = requests.get(download_url, stream=True, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise PlatoMCPError(
            f"course file download request failed (network or HTTP error): {type(e).__name__}"
        ) from None

    with resp:
        content_length = resp.headers.get("content-length")
        if content_length and int(content_length) > max_bytes:
            raise DownloadRejectedError(
                f"file size {int(content_length)} bytes exceeds max_download_mb={max_download_mb}"
            )

        try:
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    downloaded += len(chunk)
                    if downloaded > max_bytes:
                        raise DownloadRejectedError(
                            f"download exceeded max_download_mb={max_download_mb} "
                            f"while streaming (server did not report content-length)"
                        )
                    f.write(chunk)
        except DownloadRejectedError:
            dest.unlink(missing_ok=True)
            raise

        mimetype = resp.headers.get("content-type")

    return DownloadResult(path=str(dest), size_bytes=downloaded, mimetype=mimetype)
