# ---------------------------------------------------------------------------
# MIL Platform — Production Container Image
#
# Multi-stage build: a "builder" stage resolves and installs dependencies
# into a virtual environment; the final stage copies only that virtual
# environment and the application source, so the shipped image carries no
# build toolchain.
#
# This single image serves both the API process and the background workers
# — they are the same installed package, started with different commands
# (see the examples below). There is no separate worker image to keep in
# sync.
#
# Build:
#   docker build -t mil-platform:latest .
#
# Run the API:
#   docker run --rm -p 8000:8000 --env-file .env mil-platform:latest
#
# Run a worker (one process per pipeline stage):
#   docker run --rm --env-file .env mil-platform:latest python -m workers.document_pipeline
#   docker run --rm --env-file .env mil-platform:latest python -m workers.extraction_pipeline
#   docker run --rm --env-file .env mil-platform:latest python -m workers.finding_pipeline
#   docker run --rm --env-file .env mil-platform:latest python -m workers.policy_pipeline
#   docker run --rm --env-file .env mil-platform:latest python -m workers.review_pipeline
#
# Apply migrations before first start:
#   docker run --rm --env-file .env mil-platform:latest alembic upgrade head
#
# Configuration is entirely environment-driven (see .env.example and
# docs/deployment/README.md) — no secrets or environment-specific values are
# baked into this image.
# ---------------------------------------------------------------------------

# ---- Builder ---------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Build-time system dependencies for psycopg2 (compiled from source when no
# manylinux wheel matches the target platform) — removed after this stage.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml README.md ./
COPY src ./src

# Install only the runtime dependency set declared in pyproject.toml
# (no dev/test extras) into the virtual environment that ships in the
# final image.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# ---- Runtime -----------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Runtime system dependency for the psycopg2 shared library.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 mil

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY --chown=mil:mil src ./src
COPY --chown=mil:mil migrations ./migrations
COPY --chown=mil:mil alembic.ini ./alembic.ini
ENV PYTHONPATH=/app/src

USER mil

EXPOSE 8000

# GET /v1/live is the correct container healthcheck target: it never
# touches the database or providers, matching Docker's expectation that a
# healthcheck reflects process liveness, not deep readiness (see
# GET /v1/ready for that, consumed by an orchestrator's readiness probe).
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/v1/live', timeout=2)" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
