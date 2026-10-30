"""FastAPI application entry point.

Liveness plus /v1/classify on the keyword baseline. The build order in docs/adr (ADR-21) adds
/v1/health, /v1/drift and /v1/model next.
"""

from fastapi import FastAPI

from govbr_classifier import __version__
from govbr_classifier.api.rate_limit import rate_limit_middleware
from govbr_classifier.api.routes import router

app = FastAPI(
    title="gov.br complaint classifier",
    version=__version__,
    description=(
        "Classifies what a gov.br app review complains about, and says when it does not know."
    ),
)

app.middleware("http")(rate_limit_middleware)
app.include_router(router)


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    """Liveness only: 200 while the process is up.

    The platform polls this, never /v1/health (ADR-14), so it is outside the rate limit.
    """
    return {"status": "alive"}
