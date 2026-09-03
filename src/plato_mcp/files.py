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
from plato_mcp.security import default_rate_limiter

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


class DownloadLinkResult(BaseModel):
    """Returned instead of DownloadResult under streamable-http transport
    (issue #55) -- the MCP server has no local disk reachable by the end
    user there, so this hands back a direct authenticated URL instead of
    fetching the file server-side. See docs/smithery_deployment_model.md."""

    url: str
    filename: str
    warning: str


# Surfaced both in the tool docstring and on DownloadLinkResult itself --
# the response-level copy is what's most likely to reach the end user, since
# it's what the model sees in the actual tool result, not just its own
# instructions (see issue #55 plan). Token scope (this file only vs. wider
# webservice access) is intentionally left unverified here -- issue #56 is
# expected to confirm it and this string should be tightened once it does.
TOKEN_IN_URL_WARNING = (
    "This URL has a live PLATO access token embedded in it. Do not share "
    "this link or a chat transcript containing it -- whoever holds it can "
    "use it to download this file until the token is invalidated. Its "
    "exact scope (limited to this file vs. broader PLATO API access) has "
    "not yet been independently verified."
)


def _extension_of(file_url: str) -> str:
    return Path(urlparse(file_url).path).suffix.lower()


def _filename_of(file_url: str) -> str:
    return Path(urlparse(file_url).path).name


def build_course_file_download_url(client: MoodleClient, file_url: str) -> DownloadLinkResult:
    """Build a direct, authenticated download URL for a course file without
    fetching it server-side (no network beyond what get_wstoken() needs for
    login, no disk I/O at all). Used under streamable-http transport, where
    a server-side save_path would land on the container's ephemeral disk
    and never reach the actual end user (issue #55)."""
    ext = _extension_of(file_url)
    if ext not in ALLOWED_EXTENSIONS:
        raise DownloadRejectedError(f"disallowed file extension: {ext!r}")

    token = client.get_wstoken()
    separator = "&" if "?" in file_url else "?"
    download_url = f"{file_url}{separator}token={token}"

    return DownloadLinkResult(
        url=download_url, filename=_filename_of(file_url), warning=TOKEN_IN_URL_WARNING
    )


def download_course_file_for(
    client: MoodleClient, file_url: str, save_path: str, max_download_mb: int = 20
) -> DownloadResult:
    link = build_course_file_download_url(client, file_url)
    download_url = link.url

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
    default_rate_limiter.check(client.session_key)
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
