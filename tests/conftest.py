"""Shared fixtures."""

from collections.abc import Iterator

import pytest

from govbr_classifier.api import client_ip, rate_limit


@pytest.fixture(autouse=True)
def reset_rate_limit() -> Iterator[None]:
    """Give every test a fresh per-IP counter; all TestClient calls share one address."""
    rate_limit.reset()
    client_ip.reset()
    yield
