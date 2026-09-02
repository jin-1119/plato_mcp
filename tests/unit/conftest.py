"""Shared pytest fixtures for tests/unit.

`default_rate_limiter` (security.py) is a process-wide singleton, which is
exactly the point in production -- but in a test suite it means every test
shares the same token buckets, so an unrelated test earlier in the run can
exhaust the budget and make a later test fail for no reason of its own.
Reset it to a very generous configuration before every test; tests that
specifically want to exercise throttling behavior call `.reconfigure()`
themselves afterward (see test_security_audit.py).
"""

import pytest

from plato_mcp.security import default_rate_limiter


@pytest.fixture(autouse=True)
def _reset_default_rate_limiter():
    default_rate_limiter.reconfigure(
        global_capacity=10_000,
        global_refill_per_second=10_000,
        per_session_capacity=10_000,
        per_session_refill_per_second=10_000,
    )
    yield
