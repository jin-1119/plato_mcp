"""download_course_file logic (issue #28; remote-transport delivery issue #55).

fileurl values from get_course_contents (models.FileEntry) become an
authenticated download by appending ?token={wstoken} -- confirmed during
initial research: a real course PDF downloaded successfully this exact
way, no scraping needed (see PLATO_MCP_사전조사.md).
"""

import base64
from pathlib import Path
from urllib.parse import unquote, urlparse

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
    """Fallback returned under streamable-http transport only when a file is
    too large to inline as base64 (see DownloadContentResult) -- a direct
    authenticated URL the user's own browser can fetch, since the MCP server
    has no local disk reachable by the end user there. See
    docs/smithery_deployment_model.md."""

    url: str
    filename: str
    warning: str


class DownloadContentResult(BaseModel):
    """Returned under streamable-http transport for files that fit within
    INLINE_BASE64_MAX_MB (issue #55 redesign, prompted by observing a real
    Claude.ai session decode a Google Drive MCP tool's inline base64 file
    content via its code-execution/file-creation feature and present it as
    an actual downloadable/viewable file). The PLATO access token never
    leaves the server this way -- unlike DownloadLinkResult, there is no
    token-in-transcript exposure to warn about."""

    filename: str
    mimetype: str | None = None
    size_bytes: int
    content_base64: str


# Mirrors the threshold Google's own Drive MCP tool uses before it switches
# from inlining a file to chunked/reference-based delivery (see issue #55
# plan) -- comfortably above typical course PDFs (100KB-1.5MB observed
# against a real PLATO course) while keeping base64-inflated payloads out of
# the conversation context for anything large. Files above this size fall
# back to DownloadLinkResult; true chunked download (mirroring Drive's
# DownloadFileChunk) is explicitly out of scope for this pass -- see #56.
INLINE_BASE64_MAX_MB = 5

# Only surfaced on the DownloadLinkResult fallback now -- the common case
# (DownloadContentResult) never puts the token in front of the user at all,
# since the server fetches the file itself and only the decoded bytes (not
# the URL/token used to get them) reach the client.
TOKEN_IN_URL_WARNING = (
    "This file was too large to send inline, so this URL has a live PLATO "
    "access token embedded in it instead. This token is NOT scoped to this "
    "file -- confirmed by live testing (issue #56) that the same token "
    "authenticates arbitrary Moodle webservice calls (e.g. "
    "core_webservice_get_site_info), returning the account's real name, "
    "student ID, and full list of callable API functions. Do not share this "
    "link or a chat transcript containing it -- whoever holds it gets "
    "broad account-level API access, not just this one file, until the "
    "token is invalidated."
)


def _extension_of(file_url: str) -> str:
    return Path(urlparse(file_url).path).suffix.lower()


def _filename_of(file_url: str) -> str:
    return unquote(Path(urlparse(file_url).path).name)


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


def fetch_course_file_content_or_link_for(
    client: MoodleClient, file_url: str, max_inline_mb: int = INLINE_BASE64_MAX_MB
) -> DownloadContentResult | DownloadLinkResult:
    """Fetch a course file server-side and return it inline as base64 if it
    fits within max_inline_mb, else fall back to a direct download URL.

    Used under streamable-http transport instead of download_course_file_for
    (which needs a local save_path). Unlike the URL-only design this
    replaces, the common case never exposes the PLATO token to the client at
    all -- the server does the fetching, and only decoded file bytes (via
    DownloadContentResult) reach the user, the same shape Google's own Drive
    MCP tool uses for small files (see issue #55 plan)."""
    link = build_course_file_download_url(client, file_url)  # extension check + URL, no I/O yet
    max_inline_bytes = max_inline_mb * 1024 * 1024

    default_rate_limiter.check(client.session_key)
    try:
        resp = requests.get(link.url, stream=True, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise PlatoMCPError(
            f"course file download request failed (network or HTTP error): {type(e).__name__}"
        ) from None

    with resp:
        content_length = resp.headers.get("content-length")
        if content_length and int(content_length) > max_inline_bytes:
            resp.close()
            return link  # too big to inline -- URL fallback, no bytes fetched

        buf = bytearray()
        for chunk in resp.iter_content(chunk_size=65536):
            buf.extend(chunk)
            if len(buf) > max_inline_bytes:
                # Server didn't report content-length, but the body turned
                # out too big once we started reading it -- same fallback,
                # just discovered later. Not an error: a large file is a
                # normal case here, not a rejection.
                return link

        mimetype = resp.headers.get("content-type")

    return DownloadContentResult(
        filename=link.filename,
        mimetype=mimetype,
        size_bytes=len(buf),
        content_base64=base64.b64encode(bytes(buf)).decode("ascii"),
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
