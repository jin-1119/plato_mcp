"""MCP server entrypoint for PLATO (Pusan National University LMS).

Tools are registered per phase as they land (see PLAN.md / GitHub issues).
This module currently exposes zero tools — it's the Phase 0 skeleton.
"""

from mcp.server.mcpserver import MCPServer

from plato_mcp.tools import register_all

mcp = MCPServer(
    name="plato-mcp",
    description="Unofficial MCP server for PLATO (plato.pusan.ac.kr), PNU's Moodle-based LMS.",
)

register_all(mcp)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
