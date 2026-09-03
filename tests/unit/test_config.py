"""Tests for config.py's two resolution paths (issue #30).

`load_config()` must resolve env-based config for stdio/local dev
unchanged, and resolve per-request header-based config for the Smithery
streamable-http path, with headers taking precedence when both are present.
"""

import pytest

from plato_mcp.config import load_config


@pytest.fixture(autouse=True)
def _clear_pnu_env(monkeypatch):
    # dotenv_values() with no path walks up from the *caller's* stack frame
    # looking for .env, not cwd -- and that resolves to the repo root's real
    # .env (live test-account credentials) no matter where these tests run
    # from. Patch it out directly instead of trying to out-cwd it.
    monkeypatch.setattr("plato_mcp.config.dotenv_values", lambda: {})
    monkeypatch.delenv("PNU_STUDENTS_ID", raising=False)
    monkeypatch.delenv("PNU_STUDENTS_PASSWORD", raising=False)


def test_env_fallback_when_no_headers(monkeypatch):
    monkeypatch.setenv("PNU_STUDENTS_ID", "env-id")
    monkeypatch.setenv("PNU_STUDENTS_PASSWORD", "env-pw")

    config = load_config(headers=None)

    assert config.pnu_id == "env-id"
    assert config.pnu_password == "env-pw"


def test_env_fallback_when_headers_present_but_empty(monkeypatch):
    monkeypatch.setenv("PNU_STUDENTS_ID", "env-id")
    monkeypatch.setenv("PNU_STUDENTS_PASSWORD", "env-pw")

    config = load_config(headers={})

    assert config.pnu_id == "env-id"


def test_headers_win_over_env(monkeypatch):
    monkeypatch.setenv("PNU_STUDENTS_ID", "env-id")
    monkeypatch.setenv("PNU_STUDENTS_PASSWORD", "env-pw")

    config = load_config(headers={"pnu_id": "header-id", "pnu_password": "header-pw"})

    assert config.pnu_id == "header-id"
    assert config.pnu_password == "header-pw"


def test_headers_supply_optional_fields():
    config = load_config(
        headers={
            "pnu_id": "header-id",
            "pnu_password": "header-pw",
            "request_timeout_seconds": "30",
            "max_download_mb": "5",
        }
    )

    assert config.request_timeout_seconds == 30
    assert config.max_download_mb == 5


def test_no_config_anywhere_raises():
    with pytest.raises(RuntimeError):
        load_config(headers=None)
