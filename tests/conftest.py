"""Shared fixtures."""

from collections.abc import Iterator

import pytest

from govbr_classifier.api import ip_diagnostics, rate_limit


@pytest.fixture(autouse=True)
def reset_rate_limit() -> Iterator[None]:
    """Give every test a fresh per-IP counter; all TestClient calls share one address."""
    rate_limit.reset()
    ip_diagnostics.reset()
    yield
