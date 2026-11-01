"""Contract tests for the frozen response schema (ADR-02, ADR-03, ADR-21)."""

import pytest
from pydantic import ValidationError

from govbr_classifier.api.schemas import (
    ClassifyRequest,
    ItemResult,
    MultiLabelResult,
    SingleLabelResult,
)


@pytest.mark.parametrize("text", ["", "     ", "\n\t"])
def test_empty_or_whitespace_only_text_is_a_contract_error(text: str) -> None:
    with pytest.raises(ValidationError):
        ClassifyRequest(items=[{"text": text}])


@pytest.mark.parametrize("text", ["ok", "a", "👍", "?"])
def test_there_is_no_minimum_length(text: str) -> None:
    # ADR-03, 2026-11-01: short text is the model's to judge, emoji the guard's; neither is a 422.
    assert ClassifyRequest(items=[{"text": text}]).items[0].text == text


def test_text_above_limit_is_a_contract_error() -> None:
    with pytest.raises(ValidationError):
        ClassifyRequest(items=[{"text": "a" * 2001}])


def test_batch_above_limit_is_rejected_whole() -> None:
    with pytest.raises(ValidationError):
        ClassifyRequest(items=[{"text": "app ruim demais"}] * 51)


def test_unknown_request_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClassifyRequest(items=[{"text": "app ruim demais"}], engine="llm")


def test_abstention_must_carry_a_reason() -> None:
    with pytest.raises(ValidationError):
        SingleLabelResult(status="abstained")


def test_tema_prediction_cannot_be_empty() -> None:
    # Guards ADR-08: an empty prediction would be a silent fallback.
    with pytest.raises(ValidationError):
        MultiLabelResult(status="predicted", labels=[])


def test_out_of_distribution_needs_a_reason() -> None:
    with pytest.raises(ValidationError):
        ItemResult(id="1", status="out_of_distribution")
