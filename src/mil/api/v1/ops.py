"""
Operational probes and metrics — MIL API v1 (US2 Sprint 8 — Production Hardening).

Endpoints:
    GET /v1/health   — Process health: version, uptime, basic status. No auth.
    GET /v1/live     — Trivial liveness probe. No auth, no dependencies checked.
    GET /v1/ready    — Readiness probe: database connectivity, provider
                       registration, and migration state. No auth (probes
                       must not depend on the identity subsystem being up).
    GET /v1/metrics  — Basic platform metrics (requests, Copilot requests,
                       OCR jobs, workflow executions, provider failures,
                       audit events, average response time). Requires
                       ``read:operational`` permission — this exposes
                       operational volume data, not a public health signal.

``/v1/health`` and ``/v1/live`` never touch the database or providers — they
must return quickly and unconditionally so orchestrators (Kubernetes,
ECS, etc.) can distinguish "process is alive" from "process is ready to
serve traffic" (``/v1/ready``).

Dependency rule: imports from ``mil.api.deps``, ``mil.api.v1.schemas``,
``mil.kernel``, FastAPI, SQLAlchemy, and the Python standard library only.
"""

from __future__ import annotations

import pathlib
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text

from mil.api.deps import CurrentUser, DbSession, get_container
from mil.api.v1.schemas import (
    HealthResponse,
    HistogramMetric,
    LivenessResponse,
    MetricsResponse,
    ReadinessCheck,
    ReadinessResponse,
)
from mil.kernel.container import Container
from mil.kernel.metrics import InMemoryMetricEmitter
from mil.kernel.observability import MetricEmitter
from mil.kernel.providers.registry import ProviderRegistry, ProviderRegistryError
from mil.kernel.security import Permission, require_permission

router = APIRouter(tags=["System"])

_PROCESS_START = datetime.now(UTC)
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]


# ---------------------------------------------------------------------------
# GET /v1/health
# ---------------------------------------------------------------------------


@router.get(
    "/v1/health",
    summary="Health check",
    description=(
        "Basic process health: application version, process uptime, and a "
        "static 'ok' status. Does not check database or provider "
        "connectivity — see GET /v1/ready for a deep dependency check. "
        "No authentication required."
    ),
    response_model=HealthResponse,
    status_code=200,
)
def health_check() -> HealthResponse:
    """Return API process health status, version, and uptime."""
    uptime = (datetime.now(UTC) - _PROCESS_START).total_seconds()
    return HealthResponse(uptime_seconds=uptime)


# ---------------------------------------------------------------------------
# GET /v1/live
# ---------------------------------------------------------------------------


@router.get(
    "/v1/live",
    summary="Liveness probe",
    description=(
        "Trivial process liveness signal — returns 200 unconditionally if "
        "the process can handle a request at all. Checks nothing else. "
        "No authentication required."
    ),
    response_model=LivenessResponse,
    status_code=200,
)
def liveness_check() -> LivenessResponse:
    """Return a static liveness signal."""
    return LivenessResponse()


# ---------------------------------------------------------------------------
# GET /v1/ready
# ---------------------------------------------------------------------------


def _database_check(session: DbSession) -> ReadinessCheck:
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:
        return ReadinessCheck(name="database", status="fail", detail=str(exc))
    return ReadinessCheck(name="database", status="ok")


def _provider_registration_check(container: Container) -> ReadinessCheck:
    try:
        registry = container.resolve(ProviderRegistry)
        registry.validate()
    except ProviderRegistryError as exc:
        return ReadinessCheck(name="provider_registration", status="fail", detail=str(exc))
    return ReadinessCheck(name="provider_registration", status="ok")


@lru_cache(maxsize=1)
def _expected_migration_head() -> str | None:
    """
    Return the code's expected Alembic head revision.

    Cached for the process lifetime: the migration scripts on disk cannot
    change while this process is running (a new revision ships in a new
    deployment, i.e. a new process) — re-parsing ``alembic.ini`` and the
    full script directory on every ``GET /v1/ready`` poll (an orchestrator
    typically polls every few seconds, per instance) is unnecessary work on
    a hot readiness path.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(_REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_REPO_ROOT / "migrations"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def _migration_state_check(session: DbSession) -> ReadinessCheck:
    try:
        expected_head = _expected_migration_head()
    except Exception as exc:
        return ReadinessCheck(
            name="migration_state", status="fail", detail=f"Could not read migration scripts: {exc}"
        )

    try:
        row = session.execute(text("SELECT version_num FROM alembic_version")).first()
        applied_head = str(row[0]) if row is not None else None
    except Exception as exc:
        return ReadinessCheck(
            name="migration_state", status="fail", detail=f"Could not read applied migration: {exc}"
        )

    if applied_head != expected_head:
        return ReadinessCheck(
            name="migration_state",
            status="fail",
            detail=f"Database is at {applied_head!r}, code expects {expected_head!r}",
        )
    return ReadinessCheck(name="migration_state", status="ok", detail=applied_head)


@router.get(
    "/v1/ready",
    summary="Readiness probe",
    description=(
        "Deep dependency check: database connectivity, provider registration "
        "(ProviderRegistry.validate()), and migration state (applied Alembic "
        "revision matches the code's expected head). Returns 503 if any "
        "check fails. No authentication required — an orchestrator must be "
        "able to probe readiness before the identity subsystem is confirmed "
        "healthy."
    ),
    response_model=ReadinessResponse,
    responses={503: {"description": "One or more readiness checks failed"}},
)
def readiness_check(
    session: DbSession,
    container: Annotated[object, Depends(get_container)],
) -> ReadinessResponse:
    """Run all readiness checks and report pass/fail per dependency."""
    checks = [_database_check(session)]
    if isinstance(container, Container):
        checks.append(_provider_registration_check(container))
    else:
        checks.append(
            ReadinessCheck(name="provider_registration", status="fail", detail="No DI container")
        )
    checks.append(_migration_state_check(session))

    all_ok = all(check.status == "ok" for check in checks)
    body = ReadinessResponse(status="ready" if all_ok else "not_ready", checks=checks)
    return Response(  # type: ignore[return-value]
        content=body.model_dump_json(),
        media_type="application/json",
        status_code=200 if all_ok else 503,
    )


# ---------------------------------------------------------------------------
# GET /v1/metrics
# ---------------------------------------------------------------------------


@router.get(
    "/v1/metrics",
    summary="Basic platform metrics",
    description=(
        "Exposes in-process counters and histograms: HTTP requests served, "
        "Copilot requests, OCR jobs, workflow executions, provider "
        "failures, audit events, and average HTTP response time. This is a "
        "basic metrics abstraction, not distributed tracing. Requires "
        "``read:operational`` permission."
    ),
    response_model=MetricsResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_metrics(
    user: CurrentUser,
    container: Annotated[object, Depends(get_container)],
) -> MetricsResponse:
    """Return the current metrics snapshot."""
    require_permission(user, Permission.READ_OPERATIONAL)

    if not isinstance(container, Container) or not container.is_registered(MetricEmitter):
        return MetricsResponse(counters={}, histograms={})

    emitter = container.resolve(MetricEmitter)  # type: ignore[type-abstract]
    if not isinstance(emitter, InMemoryMetricEmitter):
        # A non-default MetricEmitter (e.g. an OTel exporter) owns its own
        # query interface; this endpoint only introspects the in-process default.
        return MetricsResponse(counters={}, histograms={})

    snapshot = emitter.snapshot()
    return MetricsResponse(
        counters=snapshot.counters,
        histograms={
            name: HistogramMetric(
                count=stats.count,
                sum=stats.sum,
                average=stats.average,
                minimum=stats.minimum,
                maximum=stats.maximum,
            )
            for name, stats in snapshot.histograms.items()
        },
    )
