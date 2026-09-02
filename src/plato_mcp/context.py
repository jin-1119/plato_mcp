"""Per-request MoodleClient construction, shared by every Phase 1 tool.

`_session_manager` is a single process-wide SessionManager -- that's what
lets a second tool call in the same MCP connection reuse the wstoken from
the first, instead of logging in again (see PLAN.md / issue #10).
"""

from mcp.server.mcpserver import Context

from plato_mcp.auth import PlatoSession, SessionManager
from plato_mcp.config import load_config
from plato_mcp.moodle_client import MoodleClient

_session_manager = SessionManager()


def _session_key(ctx: Context) -> str:
    # Same MCP connection -> same ctx.session object -> same key, so repeated
    # tool calls in one conversation share the cached wstoken/cookie session.
    return f"mcp-session-{id(ctx.session)}"


def get_client(ctx: Context) -> MoodleClient:
    config = load_config(ctx.headers)
    return MoodleClient(
        _session_manager,
        _session_key(ctx),
        config.pnu_id,
        config.pnu_password,
        timeout=config.request_timeout_seconds,
    )


def get_ubboard_session(ctx: Context) -> PlatoSession:
    """Ensure a cookie-session (for ubboard scraping) is ready for this connection."""
    config = load_config(ctx.headers)
    return _session_manager.ensure_ubboard_session(
        _session_key(ctx), config.pnu_id, config.pnu_password
    )


def get_userid(client: MoodleClient) -> int:
    site_info = client.call("core_webservice_get_site_info")
    return site_info["userid"]
