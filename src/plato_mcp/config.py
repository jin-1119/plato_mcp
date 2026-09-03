"""PLATO credential/config loading.

Two sources, depending on transport (see docs/smithery_deployment_model.md):

- stdio (local dev / Claude Desktop): reads PNU_STUDENTS_ID /
  PNU_STUDENTS_PASSWORD from .env / the process environment, once per call.
- streamable-http (Smithery container runtime): each request carries its
  own config as headers -- `pnu_id`, `pnu_password`, `request_timeout_seconds`,
  `max_download_mb`, matching `smithery.yaml`'s `configSchema` property names
  1:1. `QueryParamsToHeadersMiddleware` (see asgi.py) copies Smithery's
  query-param config into headers before the MCP SDK builds `Context`, since
  this SDK's streamable-http transport only threads headers through to
  `Context.headers`, not the raw query string.

`load_config(headers)` picks whichever source applies; everything else
consumes `PlatoConfig`, never the raw env vars or headers directly.
"""

import os
from collections.abc import Mapping

from dotenv import dotenv_values
from pydantic import BaseModel, ValidationError


class PlatoConfig(BaseModel):
    pnu_id: str
    pnu_password: str
    request_timeout_seconds: int = 15
    max_download_mb: int = 20


def _load_from_headers(headers: Mapping[str, str]) -> PlatoConfig | None:
    pnu_id = headers.get("pnu_id")
    pnu_password = headers.get("pnu_password")
    if not pnu_id or not pnu_password:
        return None
    kwargs = {"pnu_id": pnu_id, "pnu_password": pnu_password}
    if "request_timeout_seconds" in headers:
        kwargs["request_timeout_seconds"] = headers["request_timeout_seconds"]
    if "max_download_mb" in headers:
        kwargs["max_download_mb"] = headers["max_download_mb"]
    try:
        return PlatoConfig(**kwargs)
    except ValidationError as exc:
        # Deliberately don't interpolate `exc` here -- pydantic's ValidationError
        # message echoes back the invalid input value, which would reflect
        # arbitrary caller-supplied header content (not a credential, but
        # still unnecessary user-input reflection in an error) into the
        # response (issue #63 review).
        bad_fields = ", ".join(sorted({e["loc"][0] for e in exc.errors() if e["loc"]}))
        bad_fields = bad_fields or "pnu_id/pnu_password"
        raise RuntimeError(
            f"Invalid config supplied via request headers (check: {bad_fields})"
        ) from None


def _load_from_env() -> PlatoConfig:
    env = {**dotenv_values(), **os.environ}
    pnu_id = env.get("PNU_STUDENTS_ID")
    pnu_password = env.get("PNU_STUDENTS_PASSWORD")
    if not pnu_id or not pnu_password:
        raise RuntimeError(
            "PNU_STUDENTS_ID / PNU_STUDENTS_PASSWORD not set (.env or environment)"
        )
    return PlatoConfig(pnu_id=pnu_id, pnu_password=pnu_password)


def load_config(headers: Mapping[str, str] | None = None) -> PlatoConfig:
    """Resolve config for the current request.

    `headers` is `Context.headers` -- populated (non-None) only on HTTP
    transports. When present and it carries a `pnu_id`/`pnu_password` pair,
    that per-request config wins over the process environment, since that's
    the Smithery per-user injection path. Falls back to env/`.env` otherwise
    (local stdio, or an HTTP request with no config headers).
    """
    if headers is not None:
        from_headers = _load_from_headers(headers)
        if from_headers is not None:
            return from_headers
    return _load_from_env()
