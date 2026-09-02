"""Shared pytest fixtures for tests/unit.

Both `default_rate_limiter` (security.py) and `default_preview_tracker`
(write_tools.py) are process-wide singletons, which is exactly the point in
production -- but in a test suite it means every test shares the same
state, so an unrelated test earlier in the run can leave the budget
exhausted or a stale preview recorded and make a later test fail for no
reason of its own. Reset both before every test; tests that specifically
want to exercise throttling/confirmation behavior reconfigure or record
what they need themselves (see test_security_audit.py, test_rate_limiting.py).
"""

import pytest

from plato_mcp.security import default_rate_limiter
from plato_mcp.write_tools import default_preview_tracker


@pytest.fixture(autouse=True)
def _reset_default_rate_limiter():
    default_rate_limiter.reconfigure(
        global_capacity=10_000,
        global_refill_per_second=10_000,
        per_session_capacity=10_000,
        per_session_refill_per_second=10_000,
    )
    yield


@pytest.fixture(autouse=True)
def _reset_default_preview_tracker():
    default_preview_tracker.clear()
    yield
