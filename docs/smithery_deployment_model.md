# Smithery Python deployment model — findings (issue #29)

Researched 2026-09-03 against current Smithery docs (smithery.ai/docs), the
`smithery-ai/smithery-cookbook` repo, and the `smithery` PyPI package
(v0.4.4). This resolves the open question in `config.py`'s docstring and in
`PLAN.md` line 14.

## Two deployment paths on Smithery

Smithery supports two distinct ways to ship a server; they have very
different implications for us.

### 1. Managed Python runtime (`runtime: "python"`)

Smithery builds and runs the container for you from a `pyproject.toml` that
declares `[tool.smithery] server = "<module>:<factory>"`. The factory must
return a **`mcp.server.fastmcp.FastMCP`** instance (or the standalone
`fastmcp` package's `FastMCP`), decorated with `@smithery.server()` from the
`smithery` pip package:

```python
from mcp.server.fastmcp import FastMCP
from smithery.decorators import smithery

@smithery.server()
def create_server():
    server = FastMCP(name="Character Counter")
    @server.tool()
    def count_character(text: str, character: str) -> int:
        return text.count(character)
    return server
```

`@smithery.server(config_schema=SomeModel)` gives tools `ctx.session_config`
(parsed from URL query params, dot-notation access) for free, plus CORS.

**This path is not compatible with our current code.** We depend on
`mcp>=1.2.0` unpinned, which today resolves to `mcp` 2.1.1. In `mcp` 2.x,
`FastMCP` was renamed to `MCPServer` and **`mcp.server.fastmcp` no longer
exists** — our `server.py` already uses the new name
(`from mcp.server.mcpserver import MCPServer`). I downloaded the `smithery`
wheel (0.4.4) and inspected `smithery/server/fastmcp_patch.py` directly: it
hard-requires either `mcp.server.fastmcp.FastMCP` (old `mcp<2`) or the
separate standalone `fastmcp` PyPI package — neither of which is what we
have. Importing `smithery.decorators` in our current environment would fail
at the `mcp.server.fastmcp` import inside that module (confirmed by
reproducing the same import locally: `mcp` 2.1.1 raises
`ModuleNotFoundError` with an explicit "renamed to MCPServer" message).

Adopting this path would mean either (a) pinning `mcp<2` and reverting
`server.py`/`context.py` to the old `FastMCP`/`Context` names, or (b) adding
the separate `fastmcp` package and rewriting the server construction around
it. Both are unnecessary churn for no real benefit here.

### 2. Custom container (`runtime: "container"`) — chosen path

We bring our own `Dockerfile`; Smithery just runs it and proxies HTTP to it.
Requirements, confirmed from Smithery's container docs and multiple public
`smithery.yaml` examples:

- Server must speak **MCP Streamable HTTP** transport, mounted at **`/mcp`**,
  with CORS enabled.
- Must listen on the port given by the **`PORT`** env var (Smithery sets
  `8081` when launching the container).
- Config (from `configSchema` in `smithery.yaml`) is delivered as **query
  parameters on the request URL** (e.g. `?pnu_id=...&pnu_password=...`, or a
  single base64-encoded JSON blob for hosted/websocket-style URLs) and/or
  passthrough headers — Smithery's gateway "passes through all query
  parameters and headers to your upstream server." We read it ourselves;
  no `smithery` pip package needed.

**This is directly usable with our existing `MCPServer` class**, confirmed
by inspecting the installed SDK:

```python
mcp.run(transport="streamable-http")   # MCPServer.run() already supports this
```

and `Context` already exposes `.headers` directly (`Context.headers`,
confirmed via `dir(Context)` on the installed SDK) — so per-request config
delivered as headers or query params is reachable from any tool without
extra dependencies. Query-param reading needs a small amount of glue: pull
`ctx.request_context.request.query_params` (Starlette `Request`, since the
transport is ASGI/Starlette-based) inside a helper, rather than
`load_config()`'s current global `dotenv_values()` + `os.environ` merge,
which only works for the local/stdio case.

### `smithery.yaml` shape for the container path

```yaml
runtime: "container"
build:
  dockerfile: "Dockerfile"
  dockerBuildPath: "."
startCommand:
  type: "http"
configSchema:
  type: "object"
  properties:
    pnu_id:
      type: "string"
      description: "PNU student ID (학번)"
    pnu_password:
      type: "string"
      description: "PNU portal password"
  required: ["pnu_id", "pnu_password"]
```

(Field names should match whatever #30 settles on in `config.py` — currently
the env vars are `PNU_STUDENTS_ID`/`PNU_STUDENTS_PASSWORD`, which #30 should
reconcile with the `configSchema` property names, since those are unrelated
namespaces: one is env vars for local/stdio runs via `.env`, the other is
Smithery's per-request query params for the container runtime.)

## Decision for #30

- Keep `MCPServer` / `mcp` 2.x as-is. Do **not** adopt the `smithery` pip
  package or `runtime: "python"`.
- Add `smithery.yaml` with `runtime: "container"` (schema above) + a
  `Dockerfile` that runs `plato-mcp` with `transport="streamable-http"`
  when a Smithery-specific env var (or a CLI flag) signals container mode,
  keeping local dev on stdio by default.
- `config.py`'s `load_config()` needs a second code path: for the container
  runtime, config must be read per-request (from `Context`/query params)
  rather than once at process start from `.env`/`os.environ`, since Smithery
  injects a different config per user session, not per process. This is the
  concrete scope for #30's "wire the config schema into `config.py`
  consumption" acceptance criterion.
- `request_timeout_seconds` is currently unused anywhere in the client code
  (`moodle_client.py`/`ubboard` HTTP calls) — worth wiring in during #30 or
  flagging as a separate small gap, since it's part of the config schema but
  has no effect today.

## Sources

- https://smithery.ai/docs/build/deployments/custom-container
- https://smithery.ai/docs/build/session-config
- https://github.com/smithery-ai/smithery-cookbook (servers/python/quickstart)
- `smithery` PyPI package v0.4.4, inspected directly
  (`smithery/decorators.py`, `smithery/server/fastmcp_patch.py`)
- Installed `mcp` 2.1.1 SDK, inspected directly (`mcp.server.mcpserver`,
  `Context` attributes, `MCPServer.run()` signature)
