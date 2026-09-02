"""MCP server entrypoint for PLATO (Pusan National University LMS).

Tools are registered per phase as they land (see PLAN.md / GitHub issues).

Two run modes, selected by the `MCP_TRANSPORT` env var:
- unset / "stdio" (default): local dev, Claude Desktop -- one process per
  user, config from `.env`/environment (see config.py).
- "streamable-http": the Smithery container runtime (issue #29/#30) --
  listens on `PORT` (Smithery sets 8081), config carried per-request via
  headers/query-params (see asgi.py, config.py).
"""

import os

from mcp.server.mcpserver import MCPServer

from plato_mcp.tools import register_all

mcp = MCPServer(
    name="plato-mcp",
    description="Unofficial MCP server for PLATO (plato.pusan.ac.kr), PNU's Moodle-based LMS.",
)

register_all(mcp)


def run_http() -> None:
    """Run under Streamable HTTP, as required by Smithery's container runtime."""
    import uvicorn
    from starlette.middleware.cors import CORSMiddleware

    from plato_mcp.asgi import QueryParamsToHeadersMiddleware

    port = int(os.environ.get("PORT", "8081"))
    app = mcp.streamable_http_app(host="0.0.0.0")
    app = QueryParamsToHeadersMiddleware(app)
    app = CORSMiddleware(
        app,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


def main() -> None:
    if os.environ.get("MCP_TRANSPORT") == "streamable-http":
        run_http()
    else:
        mcp.run()


if __name__ == "__main__":
    main()
