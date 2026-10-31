"""TEMPORARY rate-limit diagnostics: they describe IP headers and never write an address."""

import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from govbr_classifier.api.ip_diagnostics import classify_address
from govbr_classifier.api.main import app
from govbr_classifier.settings import get_settings

client = TestClient(app)
BODY = {"items": [{"text": "o app trava e nao abre"}]}

# A forged test-net entry, a public client address, a Cloudflare edge, a private hop.
FORGED, CLIENT, CF_EDGE, CF_EDGE_2, PRIVATE = (
    "192.0.2.1",
    "8.8.4.4",
    "104.16.1.2",
    "172.64.3.4",
    "10.1.2.3",
)


@pytest.fixture
def diagnostics_on(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> Iterator[pytest.LogCaptureFixture]:
    monkeypatch.setattr(get_settings(), "rate_limit_diagnostics", True)
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    yield caplog


def lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("rate_limit_diag")]


def field(line: str, name: str) -> str:
    return dict(part.split("=", 1) for part in line.split()[1:])[name]


def test_off_by_default(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    client.post("/v1/classify", json=BODY, headers={"x-forwarded-for": CLIENT})
    assert lines(caplog) == []


def test_no_address_is_ever_logged(diagnostics_on: pytest.LogCaptureFixture) -> None:
    client.post(
        "/v1/classify",
        json=BODY,
        headers={
            "x-forwarded-for": f"{FORGED}, {CLIENT}, {CF_EDGE}",
            "cf-connecting-ip": CLIENT,
            "true-client-ip": CLIENT,
            "x-real-ip": PRIVATE,
            "forwarded": f"for={CF_EDGE_2}",
        },
    )
    assert len(lines(diagnostics_on)) == 1
    for address in (FORGED, CLIENT, CF_EDGE, CF_EDGE_2, PRIVATE):
        assert address not in diagnostics_on.text


def test_line_describes_the_header_shape(diagnostics_on: pytest.LogCaptureFixture) -> None:
    client.post(
        "/v1/classify",
        json=BODY,
        headers={"x-forwarded-for": f"{FORGED}, {CLIENT}, {CF_EDGE}", "cf-connecting-ip": CLIENT},
    )
    (line,) = lines(diagnostics_on)
    assert field(line, "xff_entries") == "3"
    assert field(line, "xff_classes") == "testnet,other,cloudflare"
    assert field(line, "key_class") == "cloudflare"
    assert field(line, "cf_connecting_ip_at") == "-2"
    assert field(line, "true_client_ip_at") == "absent"
    assert field(line, "present") == "x-forwarded-for,cf-connecting-ip"
    assert field(line, "testnet_in") == "x-forwarded-for"


def test_reports_when_the_key_changes_for_the_same_client(
    diagnostics_on: pytest.LogCaptureFixture,
) -> None:
    # The suspected production failure: same client, rightmost entry rotating between edges.
    for edge in (CF_EDGE, CF_EDGE_2, CF_EDGE):
        client.post("/v1/classify", json=BODY, headers={"x-forwarded-for": f"{CLIENT}, {edge}"})
    first, second, third = lines(diagnostics_on)
    assert field(first, "key_changed") == "first"
    assert field(second, "key_changed") == "true"
    assert field(third, "distinct_keys_seen") == "2"


def test_forged_cloudflare_header_is_marked(diagnostics_on: pytest.LogCaptureFixture) -> None:
    client.post("/v1/classify", json=BODY, headers={"cf-connecting-ip": "192.0.2.2"})
    assert field(lines(diagnostics_on)[0], "testnet_in") == "cf-connecting-ip"


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("192.0.2.9", "testnet"),
        ("104.16.0.1", "cloudflare"),
        ("2606:4700::1", "cloudflare"),
        ("10.0.0.1", "private"),
        ("127.0.0.1", "private"),
        ("8.8.8.8", "other"),
        ("testclient", "invalid"),
        ("", "invalid"),
    ],
)
def test_classify_address(address: str, expected: str) -> None:
    assert classify_address(address) == expected
