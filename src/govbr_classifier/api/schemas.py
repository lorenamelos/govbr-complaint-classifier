"""Request and response contract for POST /v1/classify.

This schema is FROZEN from day one (ADR-21). Improving the model changes only `model_version`.
Attributes the current model does not support abstain with reason `not_implemented`; they are never
omitted. Any change here is a breaking change and needs an ADR.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from govbr_classifier.settings import get_settings

Source = Literal["client", "scheduled_ingest"]
OodReason = Literal["language", "low_text_quality", "off_domain"]
Warning_ = Literal["length_above_training_p99"]
AbstainReason = Literal["below_threshold", "not_implemented"]

_settings = get_settings()


# ---------- Request ----------


class ReviewIn(BaseModel):
    """One item to classify. Only `text` is required (ADR-01)."""

    id: str | None = Field(default=None, max_length=128, description="Client-side id, echoed back.")
    text: str = Field(min_length=_settings.min_text_chars, max_length=_settings.max_text_chars)
    # Logged for monitoring only. Never a model feature (ADR-01).
    rating: int | None = Field(default=None, ge=1, le=5)
    app_version: str | None = Field(default=None, max_length=32)
    review_date: date | None = None

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, value: str) -> str:
        """Reject whitespace-only text as a contract violation, not as out of distribution."""
        stripped = value.strip()
        if len(stripped) < _settings.min_text_chars:
            raise ValueError(f"text must have at least {_settings.min_text_chars} non-space chars")
        return stripped


class ClassifyRequest(BaseModel):
    """A batch of 1 to MAX_BATCH_SIZE items. Any contract error rejects the whole batch (ADR-02)."""

    model_config = {"extra": "forbid"}

    items: list[ReviewIn] = Field(min_length=1, max_length=_settings.max_batch_size)
    source: Source = "client"


# ---------- Response ----------


class SingleLabelResult(BaseModel):
    """Result for a single-label attribute (bloqueio, tipo, acionabilidade)."""

    status: Literal["predicted", "abstained"]
    label: str | None = None
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    top_candidate: str | None = None
    threshold: float | None = None
    reason: AbstainReason | None = None

    @model_validator(mode="after")
    def consistent(self) -> "SingleLabelResult":
        """A prediction carries a label; an abstention carries a reason and no label."""
        if self.status == "predicted" and self.label is None:
            raise ValueError("predicted result must carry a label")
        if self.status == "abstained" and (self.label is not None or self.reason is None):
            raise ValueError("abstained result must have no label and a reason")
        return self


class MultiLabelResult(BaseModel):
    """Result for the multi-label `tema` attribute. Never falls back to `outro` (ADR-08)."""

    status: Literal["predicted", "abstained"]
    labels: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    reason: AbstainReason | None = None

    @model_validator(mode="after")
    def consistent(self) -> "MultiLabelResult":
        """A prediction has at least one label; an abstention has none and a reason."""
        if self.status == "predicted" and not self.labels:
            raise ValueError("predicted result must carry at least one label")
        if self.status == "abstained" and (self.labels or self.reason is None):
            raise ValueError("abstained result must have no labels and a reason")
        return self


class Attributes(BaseModel):
    """All four attributes are always present (ADR-21)."""

    tema: MultiLabelResult
    bloqueio: SingleLabelResult
    tipo: SingleLabelResult
    acionabilidade: SingleLabelResult


class ItemResult(BaseModel):
    """Outcome for one item: classified, or out of distribution with a reason (ADR-02, ADR-04)."""

    id: str | None
    status: Literal["classified", "out_of_distribution"]
    ood_reason: OodReason | None = None
    warnings: list[Warning_] = Field(default_factory=list)
    attributes: Attributes | None = None

    @model_validator(mode="after")
    def consistent(self) -> "ItemResult":
        """OOD items carry a reason and no attributes; classified items the opposite."""
        if self.status == "out_of_distribution" and (self.ood_reason is None or self.attributes):
            raise ValueError("out_of_distribution needs ood_reason and no attributes")
        if self.status == "classified" and (self.ood_reason is not None or self.attributes is None):
            raise ValueError("classified needs attributes and no ood_reason")
        return self


class Latency(BaseModel):
    """Server-side handler time. Client-side latency is measured outside the API (ADR-16)."""

    server: float


class ClassifyResponse(BaseModel):
    """Response for POST /v1/classify."""

    request_id: str
    model_version: str
    results: list[ItemResult]
    latency_ms: Latency
