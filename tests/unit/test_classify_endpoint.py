"""Contract tests for POST /v1/classify (ADR-02, ADR-03, ADR-21).

`test_schemas.py` proves the Pydantic models reject bad input. These tests prove the endpoint
returns the right status code for it, and that a 200 always carries all four attributes.
"""

import pytest
from fastapi.testclient import TestClient

from govbr_classifier.api.main import app
from govbr_classifier.api.schemas import ClassifyResponse
from govbr_classifier.models.keyword_baseline import MODEL_VERSION

client = TestClient(app)

NOT_IMPLEMENTED_ATTRIBUTES = ("bloqueio", "tipo", "acionabilidade")


def post(payload: dict) -> tuple[int, dict]:
    """Call the endpoint and return the status code with the parsed body."""
    response = client.post("/v1/classify", json=payload)
    return response.status_code, response.json()


# ---------- 422: the whole batch is rejected (ADR-02) ----------


@pytest.mark.parametrize(
    ("case", "payload"),
    [
        ("empty batch", {"items": []}),
        ("batch above 50", {"items": [{"text": "app ruim demais"}] * 51}),
        ("empty text", {"items": [{"text": ""}]}),
        ("whitespace only text", {"items": [{"text": "     "}]}),
        ("tabs and newlines only", {"items": [{"text": "\t\n "}]}),
        ("text above 2000 chars", {"items": [{"text": "a" * 2001}]}),
        ("missing text", {"items": [{"rating": 1}]}),
        ("unknown top-level field", {"items": [{"text": "app ruim demais"}], "engine": "llm"}),
        ("rating out of range", {"items": [{"text": "app ruim demais", "rating": 9}]}),
        ("unknown source", {"items": [{"text": "app ruim demais"}], "source": "whatever"}),
    ],
)
def test_contract_violation_returns_422(case: str, payload: dict) -> None:
    status, _ = post(payload)
    assert status == 422, case


def test_one_bad_item_rejects_the_whole_batch() -> None:
    # ADR-02: no partial answers. A batch is accepted or refused as a unit.
    status, _ = post({"items": [{"text": "o app esta muito lento"}, {"text": "   "}]})
    assert status == 422


# ---------- No minimum length: short text reaches the model (ADR-03, 2026-11-01) ----------


@pytest.mark.parametrize("text", ["ok", "ab", "a", "10"])
def test_short_text_is_valid_and_reaches_the_model(text: str) -> None:
    # The old 3-character minimum sent "ok" (about 10 thousand real reviews) to 422 and took the
    # rest of the batch with it. Now it is classified, and the model abstains if it finds nothing.
    status, body = post({"items": [{"text": text}]})

    assert status == 200
    result = body["results"][0]
    assert result["status"] == "classified"
    assert result["attributes"]["tema"] == {
        "status": "abstained",
        "labels": [],
        "scores": {},
        "reason": "below_threshold",
    }


# ---------- Out of distribution: low_text_quality (ADR-04) ----------


@pytest.mark.parametrize("text", ["👍", "👎", "😡😡😡", "???", "!!! ...", "❤️ 🙏"])
def test_text_without_letters_or_digits_is_low_text_quality(text: str) -> None:
    status, body = post({"items": [{"id": "x", "text": text}]})

    assert status == 200
    assert body["results"][0] == {
        "id": "x",
        "status": "out_of_distribution",
        "ood_reason": "low_text_quality",
        "warnings": [],
        "attributes": None,
    }


def test_one_emoji_item_does_not_take_the_batch_with_it() -> None:
    # Per item, not per batch (ADR-02): the neighbors are still classified.
    texts = ["o app esta muito lento", "👍", "ok"]
    status, body = post({"items": [{"id": str(i), "text": t} for i, t in enumerate(texts)]})

    assert status == 200
    assert [result["status"] for result in body["results"]] == [
        "classified",
        "out_of_distribution",
        "classified",
    ]


# ---------- 200: tema predicted or abstained, the rest not_implemented ----------


def test_matching_text_predicts_tema() -> None:
    payload = {"items": [{"id": "r1", "text": "não consigo fazer login, esqueci a senha"}]}
    status, body = post(payload)

    assert status == 200
    result = body["results"][0]
    assert result["id"] == "r1"
    assert result["status"] == "classified"
    assert result["ood_reason"] is None

    tema = result["attributes"]["tema"]
    assert tema["status"] == "predicted"
    assert "login_autenticacao" in tema["labels"]
    assert tema["scores"]["login_autenticacao"] == 1.0
    assert tema["reason"] is None


def test_unmatched_text_abstains_on_tema_without_falling_back() -> None:
    # ADR-08: when no label passes, the attribute abstains; it never becomes `outro`.
    status, body = post({"items": [{"text": "hmm"}]})

    assert status == 200
    tema = body["results"][0]["attributes"]["tema"]
    assert tema["status"] == "abstained"
    assert tema["reason"] == "below_threshold"
    assert tema["labels"] == []


@pytest.mark.parametrize("text", ["não consigo fazer login", "hmm", "otimo app, parabens"])
def test_other_attributes_always_abstain_with_not_implemented(text: str) -> None:
    # ADR-21: the schema is frozen, so an unimplemented attribute says so instead of being omitted.
    status, body = post({"items": [{"text": text}]})

    assert status == 200
    attributes = body["results"][0]["attributes"]
    for name in NOT_IMPLEMENTED_ATTRIBUTES:
        assert attributes[name] == {
            "status": "abstained",
            "label": None,
            "score": None,
            "top_candidate": None,
            "threshold": None,
            "reason": "not_implemented",
        }, name


def test_other_language_is_still_classified_while_its_detector_does_not_exist() -> None:
    # Only low_text_quality is built; the language and off_domain detectors are a later step.
    status, body = post({"items": [{"text": "this review is written in english"}]})

    assert status == 200
    assert body["results"][0]["status"] == "classified"


# ---------- Response shape ----------


def test_response_order_and_count_match_the_request() -> None:
    texts = ["o app esta muito lento", "hmm", "otimo app, parabens"]
    status, body = post({"items": [{"id": str(i), "text": t} for i, t in enumerate(texts)]})

    assert status == 200
    assert [result["id"] for result in body["results"]] == ["0", "1", "2"]


def test_response_validates_against_the_frozen_schema() -> None:
    status, body = post({"items": [{"text": "o app trava e nao abre"}]})

    assert status == 200
    parsed = ClassifyResponse.model_validate(body)
    assert parsed.model_version == MODEL_VERSION
    assert parsed.latency_ms.server >= 0


def test_optional_inputs_are_accepted_and_do_not_change_the_prediction() -> None:
    # ADR-01: rating, app version and date are logged for monitoring, never read as features.
    text = "o app esta muito lento"
    _, without = post({"items": [{"text": text}]})
    _, with_extras = post(
        {
            "items": [
                {"text": text, "rating": 5, "app_version": "2.3.1", "review_date": "2026-01-15"}
            ]
        }
    )

    assert without["results"][0]["attributes"] == with_extras["results"][0]["attributes"]


def test_scheduled_ingest_is_a_valid_source() -> None:
    # ADR-10: the weekly job calls this same endpoint, labeled as its own source.
    status, _ = post({"items": [{"text": "o app esta muito lento"}], "source": "scheduled_ingest"})
    assert status == 200
