"""Per-IP rate limit on POST /v1/classify (ADR-18)."""

from fastapi.testclient import TestClient

from govbr_classifier.api.main import app
from govbr_classifier.settings import get_settings

client = TestClient(app)
LIMIT = int(get_settings().rate_limit.split("/")[0])
BODY = {"items": [{"text": "o app trava e nao abre"}]}


def call(forwarded_for: str | None = None) -> int:
    """POST one valid item, optionally behind a proxy header, and return the status code."""
    headers = {"x-forwarded-for": forwarded_for} if forwarded_for else {}
    return client.post("/v1/classify", json=BODY, headers=headers).status_code


def test_call_over_the_limit_gets_429_with_retry_after() -> None:
    assert [call() for _ in range(LIMIT)] == [200] * LIMIT

    response = client.post("/v1/classify", json=BODY)
    assert response.status_code == 429
    assert "retry-after" in response.headers


def test_limited_response_reports_remaining_quota() -> None:
    response = client.post("/v1/classify", json=BODY)
    assert response.headers["x-ratelimit-limit"] == str(LIMIT)
    assert response.headers["x-ratelimit-remaining"] == str(LIMIT - 1)


def test_rejected_batches_count_toward_the_limit() -> None:
    # A 422 still costs the caller a request, so malformed floods are limited too.
    for _ in range(LIMIT):
        assert client.post("/v1/classify", json={"items": []}).status_code == 422
    assert call() == 429


def test_each_proxied_client_has_its_own_bucket() -> None:
    for _ in range(LIMIT):
        call("203.0.113.1")
    assert call("203.0.113.1") == 429
    assert call("203.0.113.2") == 200


def test_forged_leftmost_forwarded_entry_does_not_escape_the_limit() -> None:
    # The proxy appends the real address on the right; the client controls everything to its left.
    for i in range(LIMIT):
        assert call(f"10.0.0.{i}, 203.0.113.9") == 200
    assert call("10.0.0.250, 203.0.113.9") == 429


def test_liveness_is_never_limited() -> None:
    for _ in range(LIMIT + 5):
        call()
    assert client.get("/health/live").status_code == 200
