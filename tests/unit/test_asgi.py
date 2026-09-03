"""Tests for QueryParamsToHeadersMiddleware (issue #30).

Smithery's container runtime delivers per-session config as query params on
the /mcp request; the MCP SDK's streamable-http transport only threads
headers through to Context, so this shim has to copy the right query params
into headers before the wrapped app sees the request.
"""

import pytest

from plato_mcp.asgi import QueryParamsToHeadersMiddleware, RedactedAccessLogMiddleware


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


@pytest.mark.asyncio
async def test_malformed_query_string_does_not_crash_the_request():
    # issue #63 review: parse_qsl(query_string.decode("utf-8")) previously
    # raised UnicodeDecodeError unhandled on a non-UTF-8 query string.
    called = {}

    async def inner_app(scope, receive, send):
        called["ran"] = True

    app = QueryParamsToHeadersMiddleware(inner_app)
    await app(_http_scope(b"pnu_id=%FF%FE"), None, None)  # invalid UTF-8 bytes

    assert called.get("ran") is True


class TestRedactedAccessLogMiddleware:
    """issue #63: uvicorn's default access log includes the query string
    (which carries pnu_id/pnu_password in plaintext) -- this middleware
    replaces it with one that logs method/path/status only."""

    @pytest.mark.asyncio
    async def test_logs_path_without_query_string(self, caplog):
        import logging

        async def inner_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})

        app = RedactedAccessLogMiddleware(inner_app)
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/mcp",
            "query_string": b"pnu_id=202443155&pnu_password=supersecret",
        }
        async def noop_send(message):
            pass

        with caplog.at_level(logging.INFO, logger="plato_mcp.access"):
            await app(scope, None, noop_send)

        assert "supersecret" not in caplog.text
        assert "/mcp" in caplog.text
        assert "200" in caplog.text

    @pytest.mark.asyncio
    async def test_non_http_scope_passed_through_untouched(self):
        captured = {}

        async def inner_app(scope, receive, send):
            captured["scope"] = scope

        app = RedactedAccessLogMiddleware(inner_app)
        scope = {"type": "lifespan"}
        await app(scope, None, None)

        assert captured["scope"] is scope
