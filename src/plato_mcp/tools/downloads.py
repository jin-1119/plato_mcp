"""Tool: download_course_file (issue #28; remote-transport delivery issue #55).

Behavior branches on transport, detected the same way config.py/context.py
already do (headers is None under stdio, a Mapping under HTTP):
  - stdio (Claude Code / Claude Desktop): the server runs on the user's own
    machine, so it saves the file to save_path and returns DownloadResult,
    same as before #55.
  - streamable-http (Smithery container, e.g. reached via a Claude.ai
    Connector): the server's disk is not the end user's -- a save_path
    there would silently vanish into the container. So instead it returns
    DownloadLinkResult: a direct, authenticated download URL for the user's
    own browser to fetch, and save_path is rejected outright rather than
    silently ignored.
"""

from collections.abc import Mapping

from mcp.server.mcpserver import Context

from plato_mcp.config import load_config
from plato_mcp.context import get_client
from plato_mcp.errors import PlatoMCPError
from plato_mcp.files import (
    DownloadLinkResult,
    DownloadResult,
    build_course_file_download_url,
    download_course_file_for,
)
from plato_mcp.moodle_client import MoodleClient


def download_course_file_tool_for(
    client: MoodleClient,
    headers: Mapping[str, str] | None,
    file_url: str,
    save_path: str | None,
    max_download_mb: int = 20,
) -> DownloadResult | DownloadLinkResult:
    """Transport-branching logic, factored out of the `@mcp.tool()` wrapper
    so it's testable directly against a mocked client + a plain headers
    value, without needing a live MCP Context (issue #55)."""
    if headers is not None:
        if save_path is not None:
            raise PlatoMCPError(
                "save_path is not applicable when this server is running "
                "remotely -- this tool returns a download URL instead of "
                "saving a file server-side. Call it again without save_path."
            )
        return build_course_file_download_url(client, file_url)

    if save_path is None:
        raise PlatoMCPError("save_path is required when running locally (stdio).")
    return download_course_file_for(client, file_url, save_path, max_download_mb)


def register(mcp) -> None:
    @mcp.tool()
    async def download_course_file(
        ctx: Context, file_url: str, save_path: str | None = None
    ) -> DownloadResult | DownloadLinkResult:
        """Download a course file (the `fileurl` from get_course_contents).

        Running locally (stdio, e.g. Claude Code/Desktop): saves the file to
        `save_path` on this machine and returns the saved path -- `save_path`
        is required in this case.

        Running as a remote/hosted server (streamable-http, e.g. reached via
        a Claude.ai web/mobile Connector): this server's own disk is not
        reachable by you, so instead it returns a direct, authenticated
        download URL for you to open in your own browser. Do NOT pass
        `save_path` in this case -- it will be rejected. The returned URL
        embeds a live PLATO access token: do not share the link or a chat
        transcript containing it.

        Only common course-material extensions are allowed (pdf, office
        docs, images, zip, txt); local downloads over the configured size
        limit are rejected.
        """
        config = load_config(ctx.headers)
        return download_course_file_tool_for(
            get_client(ctx), ctx.headers, file_url, save_path, config.max_download_mb
        )
