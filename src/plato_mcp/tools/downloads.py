"""Tool: download_course_file (issue #28)."""

from mcp.server.mcpserver import Context

from plato_mcp.config import load_config
from plato_mcp.context import get_client
from plato_mcp.files import DownloadResult, download_course_file_for


def register(mcp) -> None:
    @mcp.tool()
    async def download_course_file(
        file_url: str, save_path: str, ctx: Context
    ) -> DownloadResult:
        """Download a course file (the `fileurl` from get_course_contents) to a local path.

        Only common course-material extensions are allowed (pdf, office docs,
        images, zip, txt); downloads over the configured size limit are rejected.
        """
        config = load_config()
        return download_course_file_for(
            get_client(ctx), file_url, save_path, config.max_download_mb
        )
