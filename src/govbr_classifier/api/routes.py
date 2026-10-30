"""Routes for POST /v1/classify.

Build step 1 (ADR-21): the keyword baseline fills `tema`; `bloqueio`, `tipo` and `acionabilidade`
are always present in the response and always abstain with `not_implemented`.

Two layers of the three in ADR-02 are active here:

- 422 rejects the whole batch. FastAPI raises it from `ClassifyRequest` validation, so the handler
  never sees a malformed batch and never partially answers one.
- Abstention is a 200 per attribute.

The middle layer, out of distribution per item, is not built yet: `guards/` is empty, so every item
that passes the contract comes back as `classified`. Adding the detectors is a later step and will
not change this schema.
"""

import time
import uuid

from fastapi import APIRouter

from govbr_classifier.api.schemas import (
    Attributes,
    ClassifyRequest,
    ClassifyResponse,
    ItemResult,
    Latency,
    MultiLabelResult,
    ReviewIn,
    SingleLabelResult,
)
from govbr_classifier.models.keyword_baseline import MODEL_VERSION, predict_tema

router = APIRouter(prefix="/v1", tags=["classify"])


def _not_implemented() -> SingleLabelResult:
    """Abstention for an attribute this model version does not serve (ADR-21)."""
    return SingleLabelResult(status="abstained", reason="not_implemented")


def _classify_tema(text: str) -> MultiLabelResult:
    """Run the baseline, abstaining when no keyword matched instead of falling back (ADR-08)."""
    labels, scores = predict_tema(text)
    if not labels:
        return MultiLabelResult(status="abstained", reason="below_threshold")
    return MultiLabelResult(status="predicted", labels=labels, scores=scores)


def _classify_item(item: ReviewIn) -> ItemResult:
    """Classify one item. `rating` and the other optional inputs are never read as features."""
    return ItemResult(
        id=item.id,
        status="classified",
        attributes=Attributes(
            tema=_classify_tema(item.text),
            bloqueio=_not_implemented(),
            tipo=_not_implemented(),
            acionabilidade=_not_implemented(),
        ),
    )


@router.post("/classify", response_model=ClassifyResponse)
def classify(request: ClassifyRequest) -> ClassifyResponse:
    """Classify 1 to 50 Portuguese review texts.

    The prediction log (ADR-17) is not wired yet; it is the next build step and will record every
    response, including the 422s this handler never sees.
    """
    started = time.perf_counter()
    results = [_classify_item(item) for item in request.items]
    elapsed_ms = (time.perf_counter() - started) * 1000

    return ClassifyResponse(
        request_id=str(uuid.uuid4()),
        model_version=MODEL_VERSION,
        results=results,
        latency_ms=Latency(server=round(elapsed_ms, 3)),
    )
