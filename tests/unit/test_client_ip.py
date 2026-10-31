"""Which address the rate limit counts a request against, behind Cloudflare and Render (ADR-18).

Production shape measured on 2026-10-31, from the left:
`X-Forwarded-For: <client>, <Cloudflare edge>, <Render internal proxy>` with the Render proxy
rotating between three private addresses, and `CF-Connecting-IP: <client>`.
"""

import logging

import pytest
from fastapi.testclient import TestClient

from govbr_classifier.api.main import app
from govbr_classifier.settings import get_settings

client = TestClient(app)
LIMIT = int(get_settings().rate_limit.split("/")[0])
BODY = {"items": [{"text": "o app trava e nao abre"}]}

CLIENT, OTHER_CLIENT = "8.8.4.4", "1.1.1.1"
CF_EDGE, CF_EDGE_2 = "172.70.1.2", "162.158.9.9"
RENDER_PROXIES = ("10.214.0.11", "10.214.0.12", "10.214.0.13")
UNLISTED_EDGE = "45.60.1.1"  # stands in for a Cloudflare range added after our copy


def call(xff: str | None, cf: str | None = None) -> int:
    headers = {}
    if xff is not None:
        headers["x-forwarded-for"] = xff
    if cf is not None:
        headers["cf-connecting-ip"] = cf
    return client.post("/v1/classify", json=BODY, headers=headers).status_code


def production_call(i: int, client_ip: str = CLIENT, edge: str = CF_EDGE) -> int:
    proxy = RENDER_PROXIES[i % len(RENDER_PROXIES)]
    return call(f"{client_ip}, {edge}, {proxy}", cf=client_ip)


def test_production_shape_counts_one_client_once() -> None:
    # Reproduces silent failure 3: keyed on the rightmost entry, this gave three counters.
    assert [production_call(i) for i in range(LIMIT)] == [200] * LIMIT
    assert production_call(LIMIT) == 429


def test_entry_point_does_not_matter() -> None:
    # The same client through two Cloudflare edges (CNF and GRU) is one counter.
    for i in range(LIMIT):
        production_call(i, edge=CF_EDGE if i % 2 else CF_EDGE_2)
    assert production_call(LIMIT, edge=CF_EDGE_2) == 429


def test_two_clients_behind_the_same_proxies_are_counted_apart() -> None:
    for i in range(LIMIT):
        production_call(i)
    assert production_call(0) == 429
    assert production_call(0, client_ip=OTHER_CLIENT) == 200


def test_forged_left_entry_does_not_escape_the_limit() -> None:
    # Measured in production: a forged entry lands left of the client, which stays at -3.
    for i in range(LIMIT):
        assert call(f"203.0.113.{i}, {CLIENT}, {CF_EDGE}, {RENDER_PROXIES[0]}", cf=CLIENT) == 200
    assert call(f"203.0.113.250, {CLIENT}, {CF_EDGE}, {RENDER_PROXIES[0]}", cf=CLIENT) == 429


def test_ipv6_clients_are_counted_per_64_prefix() -> None:
    # One home connection owns a /64 and can pick any address in it on every call.
    for i in range(LIMIT):
        address = f"2001:db8:1:2::{i + 1:x}"
        assert call(f"{address}, {CF_EDGE}, {RENDER_PROXIES[0]}", cf=address) == 200
    last = "2001:db8:1:2:ffff::1"
    assert call(f"{last}, {CF_EDGE}, {RENDER_PROXIES[0]}", cf=last) == 429
    other_prefix = "2001:db8:1:3::1"
    assert call(f"{other_prefix}, {CF_EDGE}, {RENDER_PROXIES[0]}", cf=other_prefix) == 200


def test_without_cloudflare_header_the_walk_alone_decides() -> None:
    for _ in range(LIMIT):
        call(f"{CLIENT}, {RENDER_PROXIES[0]}")
    assert call(f"{CLIENT}, {RENDER_PROXIES[1]}") == 429


# ---------- unresolved: one shared counter, and a warning without addresses ----------


def exhaust_unresolved(xff: str, cf: str | None) -> None:
    for _ in range(LIMIT):
        assert call(xff, cf=cf) == 200


def test_stale_cloudflare_list_goes_to_unresolved(caplog: pytest.LogCaptureFixture) -> None:
    # The walk stops at an edge it does not know; it disagrees with CF-Connecting-IP. Keying on the
    # edge would bring back one counter per edge, silently. Instead everyone shares one counter.
    caplog.set_level(logging.WARNING, logger="uvicorn.error")
    exhaust_unresolved(f"{CLIENT}, {UNLISTED_EDGE}, {RENDER_PROXIES[0]}", cf=CLIENT)
    assert call(f"{OTHER_CLIENT}, {UNLISTED_EDGE}, {RENDER_PROXIES[1]}", cf=OTHER_CLIENT) == 429

    warnings = [r.getMessage() for r in caplog.records if "rate_limit_unresolved" in r.getMessage()]
    assert len(warnings) == 1, "at most one warning per minute per reason"
    assert "reason=sources_disagree" in warnings[0]
    for address in (CLIENT, OTHER_CLIENT, UNLISTED_EDGE, *RENDER_PROXIES):
        assert address not in caplog.text


def test_forged_cloudflare_header_without_cloudflare_goes_to_unresolved() -> None:
    # A request that reaches the app without passing through Cloudflare can set the header freely.
    for i in range(LIMIT):
        assert call(f"{CLIENT}, {RENDER_PROXIES[0]}", cf=f"203.0.113.{i}") == 200
    assert call(f"{CLIENT}, {RENDER_PROXIES[0]}", cf="203.0.113.250") == 429


def test_only_proxies_in_the_chain_goes_to_unresolved(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="uvicorn.error")
    call(f"{CF_EDGE}, {RENDER_PROXIES[0]}")
    assert "reason=no_client_entry" in caplog.text


def test_garbage_where_the_client_should_be_goes_to_unresolved(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="uvicorn.error")
    call(f"not-an-address, {CF_EDGE}, {RENDER_PROXIES[0]}")
    assert "reason=invalid_entry" in caplog.text
