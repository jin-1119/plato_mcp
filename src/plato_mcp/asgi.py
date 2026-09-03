"""ASGI middleware for the Smithery container runtime.

Smithery's gateway delivers per-session `configSchema` values as query
parameters on the `/mcp` request URL (see docs/smithery_deployment_model.md).
This SDK's streamable-http transport only threads request *headers* through
to `Context.headers` (`mcp.server._streamable_http_modern` builds
`TransportContext(..., headers=request.headers)`, with no query-string
equivalent) -- so without this shim, query-param config would never reach
`config.py`. `QueryParamsToHeadersMiddleware` copies matching query params
into headers before the MCP app sees the request; header values win if a
name collides (a caller-supplied header is more explicit than a query
param).
"""

import logging
from urllib.parse import parse_qsl

_CONFIG_KEYS = frozenset(
    {"pnu_id", "pnu_password", "request_timeout_seconds", "max_download_mb"}
)

access_logger = logging.getLogger("plato_mcp.access")


class RedactedAccessLogMiddleware:
    """Replaces uvicorn's own access log (disabled via `access_log=False` in
    server.py) with one that never logs the query string.

    Smithery's container config-delivery model requires `pnu_id`/`pnu_password`
    to arrive as query parameters (see docs/smithery_deployment_model.md) --
    uvicorn's default access log format includes the full request line
    (method, path, *and query string*) for every request, which means the
    PLATO password would otherwise land in this server's own stdout/logs in
    plaintext on every single call, independent of any downstream proxy or
    load balancer (found via external code review, issue #63 -- the same
    class of bug as #34's credential-in-URL leak, but in a code path #34
    predates). Logs method, path (query string stripped), and status only.
    """

    def __init__(self, app):
        self._app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        method = scope.get("method", "?")
        path = scope.get("path", "?")
        status_holder: dict[str, int] = {}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        await self._app(scope, receive, send_wrapper)
        access_logger.info("%s %s -> %s", method, path, status_holder.get("status", "?"))


class QueryParamsToHeadersMiddleware:
    """Raw ASGI middleware: mirrors known query params into request headers."""

    def __init__(self, app):
        self._app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        query_string = scope.get("query_string", b"")
        if not query_string:
            await self._app(scope, receive, send)
            return

        try:
            params = dict(parse_qsl(query_string.decode("utf-8")))
        except UnicodeDecodeError:
            # Malformed (non-UTF-8) query string -- degrade to "no config
            # params found" rather than crashing the request (issue #63
            # review: this previously raised unhandled).
            await self._app(scope, receive, send)
            return
        existing_header_names = {name.lower() for name, _ in scope.get("headers", [])}

        extra_headers = [
            (key.encode("utf-8"), value.encode("utf-8"))
            for key, value in params.items()
            if key in _CONFIG_KEYS and key.encode("utf-8") not in existing_header_names
        ]
        # ASGI header names are lowercase by spec; `_CONFIG_KEYS` is already
        # lowercase, so no extra normalization needed on the query-param side.
        if extra_headers:
            scope = {**scope, "headers": [*scope.get("headers", []), *extra_headers]}

        await self._app(scope, receive, send)
