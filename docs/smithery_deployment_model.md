# Smithery Python deployment model — findings (issue #29)

Researched 2026-09-03 against current Smithery docs (smithery.ai/docs), the
`smithery-ai/smithery-cookbook` repo, and the `smithery` PyPI package
(v0.4.4). This resolves the open question in `config.py`'s docstring and in
`PLAN.md` line 14.

> **⚠️ Superseded (2026-09-04, issue #67/#68): Smithery's publish model
> changed.** Everything below this notice describes the "custom container"
> path (`runtime: "container"` in `smithery.yaml`, Smithery builds and hosts
> your `Dockerfile` from a connected GitHub repo). That path no longer exists
> in Smithery's UI or docs as of 2026-09-04 -- confirmed live by logging into
> `smithery.ai/new` and reading the current `smithery.ai/docs/build/publish`
> and `.../session-config` pages. **See the "Addendum (issue #67/#68):
> bring-your-own-hosting model" section near the end of this file for the
> current model.** The technical findings below about *this server's own
> code* (transport, config-loading, middleware) are all still accurate and
> still relevant -- only the "who builds/hosts the container" part changed.
> `smithery.yaml` is kept as historical documentation of the config schema
> fields, but nothing in the current publish flow reads it.

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

## Addendum (issue #30 implementation)

One detail the original research above didn't catch: this SDK's
streamable-http transport (`mcp/server/_streamable_http_modern.py`) builds
`TransportContext(..., headers=request.headers)` -- it only threads
**headers** through to `Context.headers`, never the raw query string. Since
Smithery's container runtime delivers `configSchema` values as query
params, a naive implementation reading only `ctx.headers` would never see
them. Fixed with `asgi.py`'s `QueryParamsToHeadersMiddleware`, a small raw
ASGI shim wrapping `mcp.streamable_http_app()` that copies the four known
config keys (`pnu_id`, `pnu_password`, `request_timeout_seconds`,
`max_download_mb`) from the query string into request headers before the
MCP app parses the request, with an explicit header of the same name always
winning over a query param. Verified end-to-end locally (not just unit
tests): booted the server with `MCP_TRANSPORT=streamable-http`, sent a
`tools/call` for `list_courses` with `?pnu_id=testid&pnu_password=testpw`
on the URL, and confirmed the server attempted a real PLATO login with
those exact fake credentials (`AuthError: PLATO login failed
(invalidlogin)`) rather than silently falling back to the real `.env`
credentials present in this dev environment.

Not verified in this environment: `docker build`/`docker run` and
`docker history` (no Docker installed here). The Dockerfile only `COPY`s
`pyproject.toml`, `README.md`, and `src/` (never `.env`), and `.dockerignore`
excludes it too as a second layer, so no credentials should end up in any
image layer -- but that should still get an actual `docker build` +
`docker history` check before #32 (public listing).

## Addendum (issue #55 redesign — remote file download)

**The gap.** `download_course_file` (issue #28) was written with only the
stdio/local case in mind: it saves the fetched file to a `save_path` on
disk and returns that path. Under the container runtime described above,
the server's disk is a Smithery-managed container's ephemeral filesystem --
not reachable by the end user at all. Discovered while manually testing the
finished tool by asking "would this same tool call work from Claude.ai
web/app chat, not just Claude Code/Desktop?" -- it would not: the file gets
saved somewhere the user can never retrieve it, silently succeeding by the
tool's own accounting while doing nothing useful for the user. Tracked as
issue #54, decomposed into #55 (this fix), #56 (live verification), #57
(this document), #59 (deferred chunked delivery).

**Design options considered for #55, and why the final shape won:**

1. **Direct authenticated URL only** (`DownloadLinkResult`-only design, the
   first version actually implemented and shipped in an earlier revision of
   this PR). The server builds `{fileurl}?token={wstoken}` and returns just
   that URL for the user's own browser to open. Simple, and avoids the
   server ever reading the file's bytes. Rejected as the *only* path once a
   real Claude.ai session was observed decoding a different MCP server's
   (Google Drive's) inline base64 tool response and presenting it as an
   actual downloadable file via its code-execution/file-creation feature --
   a strictly better experience than a raw link for the common case of a
   small course PDF, and one that never exposes a live PLATO access token
   to the user or chat transcript at all.
2. **A stateful server-side proxy/redirect endpoint** (e.g. the MCP server
   exposes its own `GET /download/{id}` route that streams the file with
   its own short-lived signed link, instead of a raw PLATO token). Rejected
   for this pass as disproportionate complexity for the common case: it
   requires the container to serve plain HTTP outside of MCP tool
   semantics, invent and store its own short-lived tokens, and handle
   expiry/cleanup -- all to solve a problem (large files) that, per real
   course material observed so far (100KB-1.5MB), barely occurs. Revisit
   only if #59's real chunked-delivery design becomes necessary.
3. **Base64-inline for small files, URL fallback for large files** (the
   shipped design, `DownloadContentResult` for files up to
   `INLINE_BASE64_MAX_MB` and `DownloadLinkResult` above it). Chosen
   because it gets the common case (small course PDFs) to the "just works,
   presented as a real file" experience with zero token exposure, while
   still handling the rare large-file case without the complexity of
   option 2. The 5MB threshold mirrors Google's own Drive MCP tool's
   inline/reference cutoff.

Live verification of this design (does Claude.ai actually decode
`DownloadContentResult` the way the Drive connector did, is the
`DownloadLinkResult` token actually as broadly-scoped as suspected, etc.)
is the subject of issue #56 -- see the addendum below for those results.

## Addendum (issue #56 live verification)

Docker was not installed when the #30 addendum above was written; it is now.
Ran the full #56 acceptance criteria against Docker Desktop on this machine.

**Confirmed working:**

- `docker build` against the existing `Dockerfile` succeeds unmodified.
- `docker run -p 8081:8081` with no credentials in the environment starts
  `MCP_TRANSPORT=streamable-http` and listens on 8081, matching the
  no-Docker verification already done for #30.
- `docker history --no-trunc` on the built image shows no `.env` file and no
  credential-bearing `ENV`/`ARG` layers -- only `pyproject.toml`, `README.md`,
  and `src/` are copied in, consistent with `.dockerignore`.
- End-to-end with real credentials: ran the container, tunnelled port 8081
  through ngrok to get a public HTTPS URL, and hit `/mcp?pnu_id=...&pnu_password=...`
  (the real Smithery container config-delivery shape) with curl -- got a real
  PLATO login and real course list back, confirming the query-param ->
  header injection path (`QueryParamsToHeadersMiddleware`) works over an
  actual public URL, not just localhost.
- Connected that same ngrok URL to Claude.ai as a custom connector (Settings
  → Connectors → Add custom connector, auth: None, credentials embedded in
  the connector URL's query string since there's no Smithery-style session
  config form outside of an actual Smithery deployment). Tools were listed
  correctly (14 tools, including `download_course_file`).
- **The core #55 question is answered: yes**, Claude.ai does decode
  `DownloadContentResult.content_base64` and present it as an actual
  downloadable file, matching the Google Drive MCP connector's behavior --
  verified against a real course file ("Ch 1.pdf", 1,415,812 bytes, well
  under the 5MB inline threshold). The mechanism: Claude's code-execution
  environment decoded the base64 by referencing the prior tool result object
  directly (e.g. `outer['content_base64']`) inside a Python snippet, rather
  than the model re-emitting the base64 text itself as output tokens -- this
  matters because a first attempt that appeared to re-type/echo the base64
  through a shell command stalled for several minutes before being
  cancelled, while the direct-reference approach completed normally. Not
  fully root-caused (Claude's code-execution internals aren't observable
  from here), but the working path is confirmed reproducible.

**Found and fixed during this testing** (unit tests didn't catch it):
`files.py`'s `_filename_of()` returned the raw, percent-encoded path segment
from the file URL (e.g. `Lecture1%20-%20Macro%282026%29.pdf` instead of
`Lecture1 - Macro(2026).pdf`), since Moodle's `fileurl` values are already
URL-encoded and `Path(urlparse(...).path).name` doesn't decode that. Fixed
with `urllib.parse.unquote()`; regression test added
(`test_build_download_url_decodes_percent_encoded_filename`). This filename
is exactly what Claude.ai's code-execution step writes the decoded file out
as, so an un-decoded name would have shipped as the visible download name.

**wstoken scope check result (was previously "not yet independently
verified" in the `DownloadLinkResult.warning` text) -- now confirmed:** the
token embedded in the URL-fallback path is **not scoped to the single
file**. Acquired a real token via `MoodleClient.get_wstoken()` and called an
unrelated webservice function, `core_webservice_get_site_info`, directly
with it -- it succeeded and returned the account's real name, student ID,
`userid`, and the full list of webservice functions the account's service is
allowed to call. In other words, this token is the same general-purpose
Moodle API credential used for every other tool in this server, not a
narrow single-file download grant. `TOKEN_IN_URL_WARNING` in `files.py` has
been updated to state this plainly instead of calling it unverified.

**Not verified — deferred, no test data available:** the `DownloadLinkResult`
fallback path itself (files >5MB) was not exercised against a real file,
because no file that large exists in the test account's actual enrolled
courses (real course PDFs observed range 100KB-1.5MB). Separately, while
manually testing a *bulk* "download every file in every course" request
through the Claude.ai connector, the response appeared to hang indefinitely
-- not reproduced against a single file, so the root cause isn't confirmed,
but two candidate causes were identified by code review (no bug found in
`files.py`/`downloads.py` itself; the fallback-on-size-exceeded logic
returns immediately once the threshold is crossed, whether from a
`content-length` header or from the streaming byte-count check):
1. `security.py`'s per-session `RateLimiter` (10-token bucket, 0.5
   tokens/sec refill) would throttle quickly under a bulk multi-file
   request (one call per course listing plus one per file), and repeated
   `RateLimitError` responses being retried by the client could look like a
   hang rather than a fast, clear failure.
2. `DownloadLinkResult.url` is designed to be opened by the *end user's own
   browser*, not fetched by the MCP client itself -- if Claude.ai's
   code-execution sandbox has no general internet egress (plausible; it did
   not need any for the inline-base64 path since no further network call
   was required there), a model attempting to fetch that URL itself from
   within the sandbox would fail or hang with no signal reaching this
   server, since the server's job (returning the link) is already complete
   by that point.

This is being left as a known, documented gap rather than force-tested with
an artificially-lowered `INLINE_BASE64_MAX_MB` against a real course, since
no real large file exists to test the fallback's actual real-world
reliability end-to-end. Revisit if/when a real large course file or a user
bug report surfaces post-deployment (tracked in #60).

## Addendum (issue #60 — root cause of the bulk-download "hang")

An external code review of the open PR stack (#53/#58/#61) flagged that
`RateLimitError` (raised by `security.py`'s `RateLimiter.check()`) is never
caught anywhere in `src/` -- a plausible cause of the bulk multi-file
download hang observed while testing #56. Following that up uncovered a
bigger, more fundamental issue underneath it.

**Root cause:** the installed MCP SDK (`mcp.server.mcpserver.tools.base`)
treats any tool-handler exception that is not one of its own `ToolError`
(or `ResourceError`, `MCPError`) types as an *unanticipated crash* -- and
for a crash, **it discards the exception's own message** and replaces it
with a generic `"Error executing tool <name>"` before it ever reaches the
model. `PlatoMCPError` (the base class for every error this project raises
deliberately -- `AuthError`, `MoodleAPIError`, `RateLimitError`,
`DownloadRejectedError`, `ScrapeError`, `WriteConfirmationError`) was a
plain `Exception` subclass, so **every one of this project's carefully
written, security-reviewed error messages was being silently discarded**,
not just `RateLimitError`'s. Confirmed live, before and after the fix,
against a running container -- calling `download_course_file` with a
disallowed extension:

- Before: `"Error executing tool download_course_file"` (no indication why)
- After: `"Error executing tool download_course_file: disallowed file extension: '.exe'"`

**Fix:** `PlatoMCPError` now inherits from the SDK's `ToolError` instead of
plain `Exception` (`errors.py`) -- a one-line base-class change that fixes
every subclass at once, rather than adding a try/except around each
individual tool function. This directly addresses the bulk-download hang:
a `RateLimitError` hit partway through a multi-file request now reaches the
model as "PLATO request rate limit exceeded for this session -- try again
shortly" instead of a content-free crash notice, so the model (and by
extension the user) can actually tell what happened and back off instead
of retrying blind.

Not changed by this fix: the `RateLimiter` defaults themselves (10 tokens
per session, 0.5/sec refill) remain unchanged -- they may still be
stricter than ideal for a legitimate "download several files from one
course" request, but that's a separate tuning question from whether the
failure is at least legible when it happens. The `DownloadLinkResult`
sandbox-egress hypothesis for the >5MB case (see the prior addendum) is
still unverified and is no longer believed to be the primary cause of the
observed hang.

## Addendum (issue #63 — HTTP-transport hardening from external code review)

An external code review of the open PR stack surfaced a critical finding
missed by everyone up to that point: `server.py`'s `run_http()` started
uvicorn with its default access log enabled, and uvicorn's default access
log format includes the full request line -- method, path, **and query
string**. Since Smithery's container config-delivery model requires
`pnu_id`/`pnu_password` to arrive as query parameters, **every single
request was logging the PLATO password in plaintext to this server's own
stdout**, independent of any downstream reverse proxy. Same class of bug
as #34 (credential-in-URL leak, fixed there by switching GET->POST), but
in a code path #34 predates and never covered -- POST isn't an option here
since query-param delivery is Smithery's platform contract, not something
this server controls.

**Verified live, before and after, against a rebuilt container hitting the
real `/mcp?pnu_id=...&pnu_password=...` endpoint:**

- Before: `INFO: 172.17.0.1:57636 - "POST /mcp?pnu_id=202443155&pnu_password=pnu202443155%21 HTTP/1.1" 200 OK`
- After: `POST /mcp -> 200`

**Fix:** `uvicorn.run(..., access_log=False)` plus a new
`RedactedAccessLogMiddleware` (`asgi.py`) that logs method, path (query
string stripped), and status only.

**Also fixed from the same review pass:**

- `QueryParamsToHeadersMiddleware`'s `parse_qsl(query_string.decode("utf-8"))`
  previously raised an unhandled `UnicodeDecodeError` on a non-UTF-8 query
  string, crashing the request. Now degrades to "no config params found."
- `config.py`'s `_load_from_headers` error message no longer interpolates
  pydantic's raw `ValidationError` text (which echoes back the invalid
  input value) -- now names only the offending field(s).
- `CORSMiddleware(allow_origins=["*"])` is intentional and now documented
  inline: safe because Smithery's gateway is the only thing that talks to
  this container directly; revisit if ever deployed standalone.

## Addendum (issue #67/#68): bring-your-own-hosting model

Discovered while starting #32 (public listing): the "custom container"
deployment path documented above -- connect a GitHub repo, Smithery builds
the `Dockerfile` and hosts the container -- **no longer exists**. Verified
live on 2026-09-04:

- Logged into `smithery.ai/new` (redirects to `smithery.ai/servers/new` once
  authenticated). The form has exactly two fields: `Namespace / Server ID`
  and **`MCP Server URL`** (placeholder `https://your-server.com/mcp`),
  described as "The HTTP URL where your MCP server is accessible." There is
  no GitHub-repo-connect option, no Dockerfile upload, no build step visible
  anywhere in this flow.
- `smithery.ai/docs/build/publish` (current content, fetched live) describes
  exactly two publishing methods: **URL-Based Publishing** ("Bring your own
  hosting -- Smithery Gateway proxies to your upstream server") and **Local
  Bundle Publishing** (`.mcpb` bundle for stdio servers, downloaded and run
  by the client locally). Neither is "Smithery builds/hosts your container."
- The old source URL this document cited,
  `smithery.ai/docs/build/deployments/custom-container`, now 404s. The docs
  site's left nav no longer has a "Deployments" section at all -- just
  "Publish" (Overview / Publish / Triggers).
- `smithery.ai/docs/build/session-config` (still current) confirms the
  config-delivery mechanics this server already relies on are unchanged:
  "For URL-published servers, Smithery Gateway passes through all query
  parameters and headers to your upstream server." This matches exactly what
  `asgi.py`'s `QueryParamsToHeadersMiddleware` + `config.py`'s
  `_load_from_headers` already implement -- **no code change needed** for
  config delivery. The doc also documents `x-from`/`x-to` metadata that lets
  a server declare that a given config field should be read from a *header*
  rather than a query parameter -- see #70, which uses this to keep
  `pnu_password` out of the request line/query string entirely in the new
  hosting layer (the same class of leak already fixed once for this
  project's own process in #34/#63, but this time at a layer outside this
  server's control -- whatever host actually runs the container).

**What this means practically:** to publish, someone must run this
container somewhere with a public HTTPS URL themselves (Cloud Run, Railway,
Render, Fly.io, etc. -- any host that accepts a Dockerfile and gives back a
public URL works, since nothing here is Smithery-specific). That URL is then
registered at `smithery.ai/new`. This project chose **Google Cloud Run**
(#69) -- generous free tier for low personal traffic, scales to zero when
idle, deploys the existing `Dockerfile` unmodified since `server.py` already
reads the `PORT` env var Cloud Run injects automatically. See #69-#73 for
the concrete deploy/publish/verify work, and
`docs/smithery_publish_guide.md` (#73) for the non-technical step-by-step
version of the same process.

## Sources

- https://smithery.ai/docs/build/deployments/custom-container
- https://smithery.ai/docs/build/session-config
- https://github.com/smithery-ai/smithery-cookbook (servers/python/quickstart)
- `smithery` PyPI package v0.4.4, inspected directly
  (`smithery/decorators.py`, `smithery/server/fastmcp_patch.py`)
- Installed `mcp` 2.1.1 SDK, inspected directly (`mcp.server.mcpserver`,
  `Context` attributes, `MCPServer.run()` signature)
