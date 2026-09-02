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

from urllib.parse import parse_qsl

_CONFIG_KEYS = frozenset(
    {"pnu_id", "pnu_password", "request_timeout_seconds", "max_download_mb"}
)


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

        params = dict(parse_qsl(query_string.decode("utf-8")))
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
