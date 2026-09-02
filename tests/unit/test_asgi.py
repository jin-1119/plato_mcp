"""Tests for QueryParamsToHeadersMiddleware (issue #30).

Smithery's container runtime delivers per-session config as query params on
the /mcp request; the MCP SDK's streamable-http transport only threads
headers through to Context, so this shim has to copy the right query params
into headers before the wrapped app sees the request.
"""

import pytest

from plato_mcp.asgi import QueryParamsToHeadersMiddleware


def _http_scope(query_string: bytes, headers: list[tuple[bytes, bytes]] | None = None) -> dict:
    return {
        "type": "http",
        "query_string": query_string,
        "headers": headers or [],
    }


@pytest.mark.asyncio
async def test_copies_known_config_params_into_headers():
    captured = {}

    async def inner_app(scope, receive, send):
        captured["headers"] = dict(scope["headers"])

    app = QueryParamsToHeadersMiddleware(inner_app)
    await app(_http_scope(b"pnu_id=abc123&pnu_password=secret"), None, None)

    assert captured["headers"][b"pnu_id"] == b"abc123"
    assert captured["headers"][b"pnu_password"] == b"secret"


@pytest.mark.asyncio
async def test_ignores_unrelated_query_params():
    captured = {}

    async def inner_app(scope, receive, send):
        captured["headers"] = dict(scope["headers"])

    app = QueryParamsToHeadersMiddleware(inner_app)
    await app(_http_scope(b"debug=true&pnu_id=abc123"), None, None)

    assert b"debug" not in captured["headers"]
    assert captured["headers"][b"pnu_id"] == b"abc123"


@pytest.mark.asyncio
async def test_existing_header_wins_over_query_param():
    captured = {}

    async def inner_app(scope, receive, send):
        captured["headers"] = dict(scope["headers"])

    app = QueryParamsToHeadersMiddleware(inner_app)
    await app(
        _http_scope(b"pnu_id=from-query", headers=[(b"pnu_id", b"from-header")]),
        None,
        None,
    )

    values = [v for k, v in captured["headers"].items() if k == b"pnu_id"]
    assert b"from-header" in values


@pytest.mark.asyncio
async def test_non_http_scope_passed_through_untouched():
    captured = {}

    async def inner_app(scope, receive, send):
        captured["scope"] = scope

    app = QueryParamsToHeadersMiddleware(inner_app)
    scope = {"type": "lifespan"}
    await app(scope, None, None)

    assert captured["scope"] is scope
