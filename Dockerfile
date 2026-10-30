# Serving image, deployed as a Docker web service on Render (ADR-16).
# Installs runtime dependencies only: no scraper, no LLM client, no notebooks.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Run as a non-root user.
RUN useradd --create-home --uid 1000 app
WORKDIR /home/app/code

COPY --chown=app pyproject.toml README.md ./
COPY --chown=app src ./src
RUN pip install .

# The package is installed non-editable, so paths derived from the source tree do not apply here.
# MODEL_DIR is unused until a trained model is served; it is set now so it never falls back silently.
ENV MODEL_DIR=/home/app/code/models/current

USER app
# The platform sets PORT (Render uses 10000); 7860 is the default for a plain `docker run`.
# Shell form so ${PORT} expands; exec so uvicorn is PID 1 and gets SIGTERM on redeploy.
EXPOSE 7860
CMD ["sh", "-c", "exec uvicorn govbr_classifier.api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
