"""
Review Pipeline Worker (US2 Sprint 6).

This is the composition root for Review jobs, dispatched by the Policy
worker (``workers.policy_pipeline``) when the POLICY stage completes. It
delegates to the Review context (create the ``ReviewSession`` handing a
Finding off for human review), advances the Orchestrator's ``WorkflowStep``
(and, since ``REVIEW`` is this workflow's last planned step, the
``WorkflowRun``), and publishes ``ReviewStarted``, ``ReviewCompleted``, and
the existing ``WorkflowCompleted`` through the Transactional Outbox. It
contains no business *rules* — no policy evaluation, no finding generation,
no evidence or document mutation. It performs job pickup, execution dispatch,
and result reporting only.

Engineering Constitution Principle I (Human Decision Authority): this worker
never renders a review verdict. It only hands a Finding off for human
review by creating a ``ReviewSession`` in ``PENDING_REVIEW`` status. Every
subsequent transition (assign, approve, reject, override) happens later,
asynchronously, outside the workflow's step machinery, driven exclusively by
an authenticated human actor through ``ReviewService`` — never by this
worker or any other AI component.

Responsibilities (and explicit non-responsibilities):
    - Loads nothing from a provider — Review has no AI/engine provider of its
      own, so there is no live-version validation to perform here (ADR-009's
      pinned-version check applies to providers; Review introduces none).
    - Creates the ``ReviewSession`` via ``ReviewService`` (never writes to
      ``finding.findings`` — only ``finding_id`` is referenced).
    - Emits ``ReviewStarted`` and ``ReviewCompleted`` (US2 Sprint 6's minimal
      additive events) and the existing ``WorkflowCompleted`` (since REVIEW
      is the workflow's final planned step) through the Transactional Outbox
      (ADR-007) — never published directly to the bus.
    - Advances the ``WorkflowStep`` and ``WorkflowRun`` state (ADR-008
      per-job Unit of Work).
    - Never evaluates Policy, never generates Findings, never mutates
      ``EvidenceItem`` or ``Document`` rows.

Per-job Unit of Work (ADR-008): everything a job writes — the ReviewSession,
its ``SESSION_STARTED`` action, the audit event (synchronous, same
transaction), the workflow step/run state, and the outbox events — commits in
the single transaction owned by ``workers.bootstrap.process_next``. A crash
before commit leaves no partial state; the redelivered job re-runs, and
idempotency (the unique constraint on ``review_sessions.finding_id``, checked
via ``ReviewRepository.exists_for_finding``) makes the replay a no-op.

Provider resolution: not applicable. Review has no ``ProviderRegistry``
dependency — no concrete provider classes exist to import here.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from mil.audit.writer import AuditWriter
from mil.kernel.errors import NotFoundError
from mil.kernel.events import ReviewCompleted, ReviewStarted, WorkflowCompleted
from mil.kernel.types import ApplicationId, FindingId, ReviewSessionId, TenantId, WorkflowRunId
from mil.orchestrator.models import StepStatus
from mil.orchestrator.repository import WorkflowRepository
from mil.outbox.repository import OutboxRepository
from mil.review.repository import ReviewRepository
from mil.review.service import ReviewService
from workers.bootstrap import build_worker_context, process_next

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from mil.kernel.container import Container
    from mil.kernel.job_queue import Job
    from mil.orchestrator.models import WorkflowRun, WorkflowStep
    from workers.bootstrap import JobHandler, WorkerContext

# REVIEW step label — the final step of the FINDING_GENERATION workflow.
REVIEW_STEP_NAME = "REVIEW"


class ReviewProcessingOutcome(enum.StrEnum):
    """
    Result of processing one Review job.

    COMPLETED    — a ReviewSession was created, the step (and run) completed,
                   and ReviewStarted/ReviewCompleted/WorkflowCompleted were
                   queued.
    ALREADY_DONE — a session already existed for this Finding; the job was a
                   replay and was treated as a no-op.
    """

    COMPLETED = "COMPLETED"
    ALREADY_DONE = "ALREADY_DONE"


@dataclass(frozen=True)
class ReviewCollaborators:
    """Session-scoped collaborators for processing one Review job."""

    review: ReviewService
    reviews: ReviewRepository
    workflows: WorkflowRepository
    outbox: OutboxRepository


class ReviewJobProcessor:
    """
    Coordinates a single Review job. Holds no business rules.

    Construct per job with session-scoped collaborators. Unlike the OCR,
    Extraction, Finding, and Policy workers, there is no external provider to
    call here, so there is no retry/dead-letter classification machinery —
    Review has no failure mode analogous to a provider outage.
    """

    def __init__(self, collaborators: ReviewCollaborators) -> None:
        self._c = collaborators

    def process(self, job: Job) -> ReviewProcessingOutcome:
        """
        Process one Review job end-to-end within the caller's transaction.

        Raises:
            NotFoundError: If the workflow run or step is missing.
        """
        finding_id = _uuid(job.payload, "finding_id")
        workflow_run_id = _uuid(job.payload, "workflow_run_id")
        step_name = str(job.payload.get("step_name", REVIEW_STEP_NAME))
        tenant_id = _uuid(job.payload, "tenant_id")
        application_id = _uuid(job.payload, "application_id")
        policy_result_id = _uuid(job.payload, "policy_result_id")
        correlation_id = str(job.payload.get("correlation_id", ""))

        run = self._c.workflows.get_by_id(workflow_run_id)
        if run is None:
            raise NotFoundError("WorkflowRun", workflow_run_id)
        step = _find_step(run, step_name)
        if step is None:
            raise NotFoundError("WorkflowStep", step_name)

        # Idempotent replay: a ReviewSession already exists for this Finding.
        # Treat as a no-op (ADR-008).
        if self._c.reviews.exists_for_finding(finding_id):
            if step.status != StepStatus.COMPLETED:
                step.mark_completed()
                if _is_last_step(run, step):
                    run.mark_completed()
                self._c.workflows.save(run)
            return ReviewProcessingOutcome.ALREADY_DONE

        step.mark_in_progress()
        step.record_retry(job.retry_count)

        # Success: hand the Finding off for human review. No AI verdict is
        # rendered here (Principle I) — only the session is created.
        session = self._c.review.start_review(
            finding_id=finding_id,
            application_id=application_id,
            tenant_id=tenant_id,
            workflow_run_id=workflow_run_id,
            policy_result_id=policy_result_id,
        )
        step.mark_completed()
        is_final_step = _is_last_step(run, step)
        if is_final_step:
            run.mark_completed()
        self._c.workflows.save(run)

        self._c.outbox.add(
            ReviewStarted(
                tenant_id=TenantId(tenant_id),
                review_session_id=ReviewSessionId(session.id),
                finding_id=FindingId(finding_id),
                application_id=ApplicationId(application_id),
                correlation_id=correlation_id,
            )
        )
        self._c.outbox.add(
            ReviewCompleted(
                tenant_id=TenantId(tenant_id),
                review_session_id=ReviewSessionId(session.id),
                finding_id=FindingId(finding_id),
                application_id=ApplicationId(application_id),
                status=session.status,
                correlation_id=correlation_id,
            )
        )
        if is_final_step:
            self._c.outbox.add(
                WorkflowCompleted(
                    tenant_id=TenantId(tenant_id),
                    workflow_run_id=WorkflowRunId(workflow_run_id),
                    application_id=ApplicationId(application_id),
                    workflow_type=run.workflow_type,
                    correlation_id=correlation_id,
                )
            )
        return ReviewProcessingOutcome.COMPLETED


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uuid(payload: dict[str, object], key: str) -> UUID:
    value = payload.get(key)
    if value is None:
        raise NotFoundError("ReviewJobPayloadField", key)
    return UUID(str(value))


def _find_step(run: WorkflowRun, step_name: str) -> WorkflowStep | None:
    return next((s for s in run.steps if s.step_name == step_name), None)


def _is_last_step(run: WorkflowRun, step: WorkflowStep) -> bool:
    return bool(run.steps) and step.step_order == run.steps[-1].step_order


# ---------------------------------------------------------------------------
# Wiring (composition root)
# ---------------------------------------------------------------------------


def build_review_collaborators(session: Session, container: Container) -> ReviewCollaborators:
    """
    Build the session-scoped collaborators for one Review job.

    Unlike the other pipeline workers, Review has no provider to resolve
    from the DI container — ``container`` is accepted only for interface
    consistency with the other ``build_*_collaborators`` composition roots.
    """
    del container  # Review has no provider; kept for interface consistency.
    audit = AuditWriter(session)
    review_repository = ReviewRepository(session)
    review_service = ReviewService(review_repository, audit)
    return ReviewCollaborators(
        review=review_service,
        reviews=review_repository,
        workflows=WorkflowRepository(session),
        outbox=OutboxRepository(session),
    )


def make_review_handler(container: Container) -> JobHandler:
    """
    Build a ``JobHandler`` that processes Review jobs.

    The returned handler builds session-scoped collaborators per job and runs
    the ``ReviewJobProcessor``. It does not commit — the bootstrap harness
    owns the transaction (per-job Unit of Work).
    """

    def handler(session: Session, job: Job) -> None:
        collaborators = build_review_collaborators(session, container)
        processor = ReviewJobProcessor(collaborators)
        processor.process(job)

    return handler


def run_drain(ctx: WorkerContext, handler: JobHandler, *, max_iterations: int | None = None) -> int:
    """
    Process available jobs until the queue is empty (or ``max_iterations``).

    Returns the number of jobs processed. Bounded by ``max_iterations`` when
    supplied (used by tests); unbounded draining stops when the queue is empty.
    """
    processed = 0
    while max_iterations is None or processed < max_iterations:
        if not process_next(ctx, handler):
            break
        processed += 1
    return processed


def main() -> None:  # pragma: no cover - process entry point
    """Entry point for the Review pipeline worker process."""
    ctx = build_worker_context()
    handler = make_review_handler(ctx.container)
    while True:
        if not process_next(ctx, handler):
            break


if __name__ == "__main__":  # pragma: no cover
    main()
