"""
Operational Dashboard REST endpoints — MIL API v1 (spec 005-enterprise-
platform §10, Wave 3).

Endpoints:
    GET /v1/operational/queue-depth   Job queue depth per workflow type/status
    GET /v1/operational/poison-jobs   Steps that exceeded their retry ceiling
    GET /v1/operational/funnel        Application-lifecycle funnel

Complements the existing `GET /v1/metrics` (`mil.api.v1.ops`) rather than
duplicating it — that endpoint covers in-process request/Copilot/OCR
counters; this module covers real, persisted `WorkflowRun`/`WorkflowStep`/
`MortgageApplication` aggregates. `OperationalWorkspace`'s methods
self-check `read:operational`.

Dependency rule: imports from `mil.api.deps`, `mil.api.v1.schemas`, FastAPI,
and the Python standard library only.
"""

from __future__ import annotations

from fastapi import APIRouter

from mil.api.deps import CurrentUser, OperationalWorkspaceDep  # noqa: TC001
from mil.api.v1.schemas import (
    ApplicationFunnelResponse,
    ApplicationFunnelRowResponse,
    JobQueueHealthResponse,
    PoisonJobListResponse,
    PoisonJobResponse,
    QueueDepthResponse,
    QueueDepthRowResponse,
)

router = APIRouter(prefix="/v1/operational", tags=["Operational"])


@router.get(
    "/queue-depth",
    summary="Job queue depth per workflow type and status",
    response_model=QueueDepthResponse,
    responses={403: {"description": "Insufficient permissions"}},
)
def get_queue_depth(user: CurrentUser, workspace: OperationalWorkspaceDep) -> QueueDepthResponse:
    rows = workspace.get_queue_depth(user)
    return QueueDepthResponse(
        items=[
            QueueDepthRowResponse(workflow_type=r.workflow_type, status=r.status, count=r.count)
            for r in rows
        ]
    )


@router.get(
    "/poison-jobs",
    summary="Workflow steps that exceeded their retry ceiling",
    response_model=PoisonJobListResponse,
    responses={403: {"description": "Insufficient permissions"}},
)
def get_poison_jobs(user: CurrentUser, workspace: OperationalWorkspaceDep) -> PoisonJobListResponse:
    steps = workspace.get_poison_jobs(user)
    return PoisonJobListResponse(
        items=[
            PoisonJobResponse(
                id=step.id,
                workflow_run_id=step.workflow_run_id,
                step_name=step.step_name,
                status=step.status,
                retry_count=step.retry_count,
                max_retries=step.max_retries,
                error_code=step.error_code,
                error_message=step.error_message,
                updated_at=step.updated_at,
            )
            for step in steps
        ]
    )


@router.get(
    "/funnel",
    summary="Application-lifecycle funnel (count and average time since update per status)",
    response_model=ApplicationFunnelResponse,
    responses={403: {"description": "Insufficient permissions"}},
)
def get_funnel(user: CurrentUser, workspace: OperationalWorkspaceDep) -> ApplicationFunnelResponse:
    rows = workspace.get_funnel(user)
    return ApplicationFunnelResponse(
        items=[
            ApplicationFunnelRowResponse(
                status=r.status,
                count=r.count,
                avg_seconds_since_updated=r.avg_seconds_since_updated,
            )
            for r in rows
        ]
    )


@router.get(
    "/job-queue-health",
    summary="Real, process-wide job queue health (pending/processing/dead-letter counts)",
    response_model=JobQueueHealthResponse,
    responses={403: {"description": "Insufficient permissions"}},
)
def get_job_queue_health(
    user: CurrentUser, workspace: OperationalWorkspaceDep
) -> JobQueueHealthResponse:
    health = workspace.get_job_queue_health(user)
    return JobQueueHealthResponse(
        pending_count=health.pending_count,
        processing_count=health.processing_count,
        dead_letter_count=health.dead_letter_count,
    )
