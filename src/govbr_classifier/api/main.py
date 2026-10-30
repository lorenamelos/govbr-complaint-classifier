"""FastAPI application entry point.

Only the liveness route exists in this skeleton. The build order in docs/adr (ADR-21) adds
/v1/classify with the keyword baseline next, then /v1/health, /v1/drift and /v1/model.
"""

from fastapi import FastAPI

from govbr_classifier import __version__

app = FastAPI(
    title="gov.br complaint classifier",
    version=__version__,
    description=(
        "Classifies what a gov.br app review complains about, and says when it does not know."
    ),
)


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    """Liveness only: 200 while the process is up.

    The platform polls this, never /v1/health (ADR-14).
    """
    return {"status": "alive"}
