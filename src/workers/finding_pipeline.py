"""
Finding Pipeline Worker (US2 Sprint 4).

This is the composition root for Finding jobs. It delegates to the Finding
context (execute inference over the evidence collected for an application,
persist the immutable ``Finding``), advances the Orchestrator's
``WorkflowStep``, and publishes ``FindingGenerated`` through the Transactional
Outbox. It contains no business *rules* — no policy evaluation, no human
review, no evidence mutation, no document mutation. It performs job pickup,
execution dispatch, and result reporting only.

Trigger (ADR-009): per the accepted architecture, Finding generation is
triggered by the ``MortgageApplication`` DRAFT → SUBMITTED transition and
evaluates *all* of an application's evidence at that point — never per
document. ``start_finding_generation_workflow`` (below) is the composition
function the API layer calls, in the same request transaction as the
submission, to start the dedicated ``FINDING_GENERATION`` workflow run and
dispatch its single ``FINDING`` step job. This worker module then consumes
that job exactly like ``workers.document_pipeline`` consumes OCR jobs.

Responsibilities (and explicit non-responsibilities):
    - Resolves ``InferenceProvider`` exclusively via ``ProviderRegistry``.
    - Loads every ``EvidenceItem`` for the application (never re-runs
      extraction, never mutates evidence).
    - Executes inference and persists the immutable ``Finding`` via
      ``FindingService`` (full provider-version attribution — Principle XII).
    - Emits the existing typed ``FindingGenerated`` ``DomainEvent`` through the
      Transactional Outbox (ADR-007) — never published directly to the bus.
    - Advances the ``WorkflowStep`` state (ADR-008 per-job Unit of Work), and,
      on success, dispatches the workflow's next planned step (``POLICY``,
      US2 Sprint 5) exactly as ``workers.document_pipeline`` dispatches
      ``EXTRACTION`` after ``OCR`` — or completes the ``WorkflowRun`` if
      ``FINDING`` is the last planned step (older runs / tests with no
      Policy step planned).
    - Never evaluates Policy, never performs human review, never mutates
      ``EvidenceItem`` or ``Document`` rows.

Per-job Unit of Work (ADR-008): everything a job writes — the Finding, the
audit event (synchronous, same transaction), the workflow step/run state, and
the outbox event — commits in the single transaction owned by
``workers.bootstrap.process_next``. A crash before commit leaves no partial
state; the redelivered job re-runs, and idempotency (the unique constraint on
``(application_id, model_version)``, checked via
``FindingRepository.exists_for_application_and_version``) makes the replay a
no-op.

Version pinning (ADR-009 / Principle XII): the workflow run pins the inference
engine version at creation (``run.pinned_versions.inference``). This worker
validates that the registered ``InferenceProvider``'s live ``version()``
matches the pinned value before running — a mismatch is a structural
configuration drift, not a transient fault, and is therefore terminal
(non-retryable). The already-pinned extraction and policy versions
(``run.pinned_versions.extraction`` / ``.policy``) are read, never
recomputed, and recorded as passive attribution — reading a pinned string is
not "evaluating policy".

Provider resolution is exclusively through the DI container (``ProviderRegistry``).
Concrete provider classes are never imported or instantiated here.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

from mil.audit.writer import AuditWriter
from mil.evidence.repository import EvidenceRepository
from mil.finding.repository import FindingRepository
from mil.finding.service import FindingService
from mil.kernel.errors import (
    NotFoundError,
    ProviderError,
    ProviderVersionMissingError,
    ValidationError,
)
from mil.kernel.events import FindingGenerated, WorkflowStepFailed
from mil.kernel.job_queue import Job, JobQueue
from mil.kernel.metrics import MetricName
from mil.kernel.observability import MetricEmitter, NoOpMetricEmitter
from mil.kernel.providers.inference import EvidenceEntry, InferenceContext
from mil.kernel.providers.registry import ProviderRegistry
from mil.kernel.types import ApplicationId, FindingId, TenantId, WorkflowRunId
from mil.orchestrator.models import (
    PinnedVersions,
    StepStatus,
    WorkflowRun,
    WorkflowStatus,
    WorkflowStep,
)
from mil.orchestrator.repository import WorkflowRepository
from mil.orchestrator.retry import (
    DeadLetterSink,
    NoOpDeadLetterSink,
    RetryDecision,
    RetryPolicy,
)
from mil.orchestrator.service import IntelligenceOrchestrator
from mil.outbox.repository import OutboxRepository
from workers.bootstrap import build_worker_context, process_next

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.orm import Session

    from mil.evidence.models import EvidenceItem
    from mil.kernel.container import Container
    from mil.kernel.providers.inference import InferenceProvider
    from workers.bootstrap import JobHandler, WorkerContext

# FINDING step label — the first step of the FINDING_GENERATION workflow.
FINDING_STEP_NAME = "FINDING"

# POLICY step label — dispatched after FINDING completes (US2 Sprint 5).
# REVIEW step label — dispatched after POLICY completes (US2 Sprint 6).
# Duplicated as literals here (rather than imported from
# workers.policy_pipeline / workers.review_pipeline) to avoid a cross-worker
# import dependency; the workers agree on this job-payload contract, not on
# shared code.
_POLICY_STEP_NAME = "POLICY"
_REVIEW_STEP_NAME = "REVIEW"

# Workflow type dispatched on the MortgageApplication DRAFT -> SUBMITTED
# transition (ADR-009).
FINDING_WORKFLOW_TYPE = "FINDING_GENERATION"

# Job type for every dispatched WorkflowStep job (orchestrator convention).
_JOB_TYPE_WORKFLOW_STEP = "workflow_step"

# Fixed prompt version for this sprint's generic evidence-assessment prompt.
# No prompt-management system exists yet; this is a passive attribution
# constant, not a policy decision.
_FINDING_PROMPT_VERSION = "finding-generation-prompt-v1"

_NO_EVIDENCE_SENTINEL = "n/a"


class FindingProcessingOutcome(enum.StrEnum):
    """
    Result of processing one Finding job.

    COMPLETED       — inference ran, the Finding was persisted, the step (and
                      run) completed, and ``FindingGenerated`` was queued.
    ALREADY_DONE    — a Finding already existed for (application, model
                      version); the job was a replay and was treated as a no-op.
    FAILED_TERMINAL — inference failed permanently; the step is FAILED and
                      ``WorkflowStepFailed`` was queued.

    A retryable failure with attempts remaining does not produce an outcome — it
    propagates so the Unit of Work rolls back and the queue requeues the job.
    """

    COMPLETED = "COMPLETED"
    ALREADY_DONE = "ALREADY_DONE"
    FAILED_TERMINAL = "FAILED_TERMINAL"


@dataclass(frozen=True)
class FindingCollaborators:
    """Session-scoped collaborators for processing one Finding job."""

    inference_provider: InferenceProvider
    evidence_items: EvidenceRepository
    finding: FindingService
    findings: FindingRepository
    workflows: WorkflowRepository
    outbox: OutboxRepository
    job_queue: JobQueue
    metrics: MetricEmitter = field(default_factory=NoOpMetricEmitter)


class FindingJobProcessor:
    """
    Coordinates a single Finding job. Holds no business rules.

    Construct per job with session-scoped collaborators plus the retry policy
    and dead-letter sink (process-scoped extension points, ADR-008).
    """

    def __init__(
        self,
        collaborators: FindingCollaborators,
        *,
        retry_policy: RetryPolicy | None = None,
        dead_letter: DeadLetterSink | None = None,
    ) -> None:
        self._c = collaborators
        self._retry = retry_policy if retry_policy is not None else RetryPolicy()
        self._dead_letter = dead_letter if dead_letter is not None else NoOpDeadLetterSink()

    def process(self, job: Job) -> FindingProcessingOutcome:
        """
        Process one Finding job end-to-end within the caller's transaction.

        Raises:
            NotFoundError: If the workflow run or step is missing.
            ValidationError: If the application has no evidence to evaluate.
            ProviderError: Re-raised for a retryable failure with attempts
                remaining, so the Unit of Work rolls back and the job requeues.
        """
        application_id = _uuid(job.payload, "application_id")
        workflow_run_id = _uuid(job.payload, "workflow_run_id")
        step_name = str(job.payload.get("step_name", FINDING_STEP_NAME))
        tenant_id = _uuid(job.payload, "tenant_id")
        correlation_id = str(job.payload.get("correlation_id", ""))

        run = self._c.workflows.get_by_id(workflow_run_id)
        if run is None:
            raise NotFoundError("WorkflowRun", workflow_run_id)
        step = _find_step(run, step_name)
        if step is None:
            raise NotFoundError("WorkflowStep", step_name)

        # ADR-009 / Principle XII: validate the live provider matches the
        # version pinned to this run at creation — never trust the provider's
        # live version() output as the source of truth.
        expected_version = run.pinned_versions.inference
        provider_version = self._c.inference_provider.version()
        self._validate_provider_version(provider_version, expected_version)

        # Idempotent replay: a Finding already generated deterministically for
        # this (application, model version). Treat as a no-op (ADR-008).
        if self._c.findings.exists_for_application_and_version(application_id, expected_version):
            if step.status != StepStatus.COMPLETED:
                step.mark_completed()
                if _is_last_step(run, step) and run.status_enum == WorkflowStatus.RUNNING:
                    run.mark_completed()
                self._c.workflows.save(run)
            return FindingProcessingOutcome.ALREADY_DONE

        evidence_items = self._c.evidence_items.get_for_application(application_id)
        if not evidence_items:
            raise ValidationError(
                "Cannot generate a Finding: application has no evidence",
                field="application_id",
            )

        step.mark_in_progress()
        step.record_retry(job.retry_count)

        try:
            context = _build_context(application_id, evidence_items, run.pinned_versions.prompt)
            result = self._c.inference_provider.infer(context)
            self._validate_result_version(result.model_version, provider_version)
        except ProviderError as exc:
            return self._handle_failure(
                run=run,
                step=step,
                workflow_run_id=workflow_run_id,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                job=job,
                exc=exc,
            )

        # Success: persist the immutable Finding, complete the step (and run,
        # since FINDING is the sole step), publish.
        finding = self._c.finding.generate_finding(
            application_id=application_id,
            tenant_id=tenant_id,
            workflow_run_id=workflow_run_id,
            evidence_items=evidence_items,
            inference_result=result,
            extraction_version=run.pinned_versions.extraction,
        )
        step.mark_completed()
        if _is_last_step(run, step):
            run.mark_completed()
        self._c.workflows.save(run)
        self._c.outbox.add(
            FindingGenerated(
                tenant_id=TenantId(tenant_id),
                finding_id=FindingId(finding.id),
                application_id=ApplicationId(application_id),
                finding_type=finding.finding_type,
                policy_version=run.pinned_versions.policy,
                correlation_id=correlation_id,
            )
        )
        self._dispatch_next_step(
            run=run,
            completed_step=step,
            application_id=application_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            finding_id=finding.id,
        )
        return FindingProcessingOutcome.COMPLETED

    def _dispatch_next_step(
        self,
        *,
        run: WorkflowRun,
        completed_step: WorkflowStep,
        application_id: UUID,
        tenant_id: UUID,
        correlation_id: str,
        finding_id: UUID,
    ) -> None:
        """
        Enqueue the job for the next planned step (``POLICY``, US2 Sprint 5),
        if any.

        Mirrors ``workers.document_pipeline``'s OCR -> EXTRACTION dispatch:
        same job type, same idempotency-key derivation. A run with no further
        planned steps (e.g. single-step FINDING_GENERATION runs predating
        Sprint 5) is a no-op.
        """
        next_step = next(
            (s for s in run.steps if s.step_order == completed_step.step_order + 1), None
        )
        if next_step is None or next_step.status != StepStatus.PENDING:
            return
        self._c.job_queue.enqueue(
            Job(
                job_type=_JOB_TYPE_WORKFLOW_STEP,
                idempotency_key=f"{run.id}:{next_step.step_name}",
                payload={
                    "workflow_run_id": str(run.id),
                    "step_id": str(next_step.id),
                    "step_name": next_step.step_name,
                    "application_id": str(application_id),
                    "tenant_id": str(tenant_id),
                    "correlation_id": correlation_id,
                    "finding_id": str(finding_id),
                },
                max_retries=next_step.max_retries,
            )
        )

    # ------------------------------------------------------------------
    # Failure handling (ADR-008 retry classification)
    # ------------------------------------------------------------------

    def _handle_failure(
        self,
        *,
        run: WorkflowRun,
        step: WorkflowStep,
        workflow_run_id: UUID,
        tenant_id: UUID,
        correlation_id: str,
        job: Job,
        exc: ProviderError,
    ) -> FindingProcessingOutcome:
        decision = self._retry.classify(
            exc, retry_count=job.retry_count, max_retries=job.max_retries
        )
        if decision is RetryDecision.RETRY:
            # Re-raise so the Unit of Work rolls back and the queue requeues.
            raise exc

        # Terminal: record the permanent failure within this transaction.
        if decision is RetryDecision.RETRIES_EXHAUSTED:
            self._dead_letter.record(job, exc)

        self._c.metrics.increment(MetricName.PROVIDER_FAILURES_TOTAL)
        step.record_retry(job.retry_count)
        step.mark_failed(error_code=exc.code, error_message=exc.message)
        run.mark_failed()
        self._c.workflows.save(run)
        self._c.outbox.add(
            WorkflowStepFailed(
                tenant_id=TenantId(tenant_id),
                workflow_run_id=WorkflowRunId(workflow_run_id),
                step_name=step.step_name,
                error_code=exc.code,
                error_message=exc.message,
                retry_count=job.retry_count,
                correlation_id=correlation_id,
            )
        )
        return FindingProcessingOutcome.FAILED_TERMINAL

    @staticmethod
    def _validate_provider_version(reported_version: str, expected_version: str) -> None:
        """
        Enforce the pinned-version contract (ADR-009 / Principle XII).

        A missing or drifted provider version relative to the version pinned
        on the workflow run is a structural violation, not a transient fault —
        it is terminal (non-retryable).
        """
        if not reported_version:
            raise ProviderVersionMissingError("InferenceProvider", "version")
        if reported_version != expected_version:
            raise ProviderError(
                f"InferenceProvider version mismatch: registered provider reports "
                f"{reported_version!r}, workflow run pinned {expected_version!r}",
                provider_name="InferenceProvider",
                retryable=False,
            )

    @staticmethod
    def _validate_result_version(result_version: str, expected_version: str) -> None:
        """
        Enforce that the returned ``InferenceResult`` reports the same version
        as the provider's own ``version()`` — an internal consistency
        contract violation is terminal (non-retryable).
        """
        if not result_version:
            raise ProviderVersionMissingError("InferenceProvider", "model_version")
        if result_version != expected_version:
            raise ProviderError(
                f"InferenceProvider returned an InferenceResult with model_version "
                f"{result_version!r}, expected {expected_version!r}",
                provider_name="InferenceProvider",
                retryable=False,
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uuid(payload: dict[str, object], key: str) -> UUID:
    value = payload.get(key)
    if value is None:
        raise NotFoundError("FindingJobPayloadField", key)
    return UUID(str(value))


def _find_step(run: WorkflowRun, step_name: str) -> WorkflowStep | None:
    return next((s for s in run.steps if s.step_name == step_name), None)


def _is_last_step(run: WorkflowRun, step: WorkflowStep) -> bool:
    return bool(run.steps) and step.step_order == run.steps[-1].step_order


def _build_context(
    application_id: UUID, evidence_items: Sequence[EvidenceItem], prompt_version: str
) -> InferenceContext:
    """Build the scoped ``InferenceContext`` from an application's evidence."""
    entries = tuple(
        EvidenceEntry(
            evidence_ref=str(item.id),
            field_name=item.evidence_type,
            field_value=item.value_text or "",
            confidence=float(item.extraction_confidence),
            source_ref=str(item.document_id),
            page_number=item.page_number or 0,
        )
        for item in evidence_items
    )
    return InferenceContext(
        application_id=str(application_id),
        evidence_items=entries,
        query=(
            f"Assess the collected evidence for application {application_id} and produce a finding."
        ),
        prompt_version=prompt_version,
    )


def _derive_extraction_version(evidence_items: Sequence[EvidenceItem]) -> str:
    """
    Derive a single pinned extraction-version string from an application's
    collected evidence.

    No single extraction pass covers a whole application (each document is
    extracted independently, US2 Sprint 3), so this is the sorted, unique,
    comma-joined set of ``extraction_model_version`` values across all
    evidence — deterministic and reproducible for a given evidence set.
    ``"n/a"`` when no evidence exists yet.
    """
    if not evidence_items:
        return _NO_EVIDENCE_SENTINEL
    versions = sorted({item.extraction_model_version for item in evidence_items})
    return ",".join(versions)


# ---------------------------------------------------------------------------
# Trigger (composition root for the DRAFT -> SUBMITTED transition, ADR-009)
# ---------------------------------------------------------------------------


def start_finding_generation_workflow(
    session: Session,
    container: Container,
    *,
    application_id: UUID,
    tenant_id: UUID,
    correlation_id: str | None = None,
) -> WorkflowRun:
    """
    Start (or return the existing) ``FINDING_GENERATION`` workflow run for an
    application.

    Per ADR-009, Finding generation is triggered by the ``MortgageApplication``
    DRAFT -> SUBMITTED transition and evaluates *all* of the application's
    evidence at that point, never per document. The caller (the composition
    root handling the submit use case) is expected to invoke this within the
    same database transaction as the application's state change, so the
    ``WorkflowRun``, its planned ``FINDING`` step, and its ``WorkflowStarted``
    outbox event commit atomically with the submission (ADR-007 / ADR-008).

    Idempotent (ADR-008): the idempotency key is deterministic per application,
    so a repeat call (e.g. a retried request) returns the existing run rather
    than creating a duplicate or re-dispatching the job.
    """
    registry = container.resolve(ProviderRegistry)
    inference_version = registry.get_inference().version()
    policy_version = registry.get_policy().version()

    evidence_items = EvidenceRepository(session).get_for_application(application_id)
    pinned = PinnedVersions(
        policy=policy_version,
        extraction=_derive_extraction_version(evidence_items),
        inference=inference_version,
        prompt=_FINDING_PROMPT_VERSION,
    )

    orchestrator = IntelligenceOrchestrator(
        WorkflowRepository(session),
        OutboxRepository(session),
        container.resolve(JobQueue),
    )
    return orchestrator.start_workflow(
        tenant_id=tenant_id,
        application_id=application_id,
        workflow_type=FINDING_WORKFLOW_TYPE,
        idempotency_key=f"{FINDING_WORKFLOW_TYPE}:{application_id}",
        step_names=[FINDING_STEP_NAME, _POLICY_STEP_NAME, _REVIEW_STEP_NAME],
        pinned_versions=pinned,
        correlation_id=correlation_id,
    )


# ---------------------------------------------------------------------------
# Wiring (composition root for job processing)
# ---------------------------------------------------------------------------


def build_finding_collaborators(session: Session, container: Container) -> FindingCollaborators:
    """
    Build the session-scoped collaborators for one Finding job.

    Providers are resolved exclusively through the DI container's
    ``ProviderRegistry`` — concrete provider classes are never imported here.
    """
    registry = container.resolve(ProviderRegistry)
    inference_provider = registry.get_inference()
    metrics = container.resolve(MetricEmitter)  # type: ignore[type-abstract]

    audit = AuditWriter(session, metrics=metrics)
    finding_repository = FindingRepository(session)
    finding_service = FindingService(finding_repository, audit)
    return FindingCollaborators(
        inference_provider=inference_provider,
        evidence_items=EvidenceRepository(session),
        finding=finding_service,
        findings=finding_repository,
        workflows=WorkflowRepository(session),
        outbox=OutboxRepository(session),
        job_queue=container.resolve(JobQueue),
        metrics=metrics,
    )


def make_finding_handler(
    container: Container,
    *,
    retry_policy: RetryPolicy | None = None,
    dead_letter: DeadLetterSink | None = None,
) -> JobHandler:
    """
    Build a ``JobHandler`` that processes Finding jobs.

    The returned handler builds session-scoped collaborators per job and runs
    the ``FindingJobProcessor``. It does not commit — the bootstrap harness
    owns the transaction (per-job Unit of Work).
    """

    def handler(session: Session, job: Job) -> None:
        collaborators = build_finding_collaborators(session, container)
        processor = FindingJobProcessor(
            collaborators, retry_policy=retry_policy, dead_letter=dead_letter
        )
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
    """Entry point for the Finding pipeline worker process."""
    ctx = build_worker_context()
    handler = make_finding_handler(ctx.container)
    while True:
        if not process_next(ctx, handler):
            break


if __name__ == "__main__":  # pragma: no cover
    main()
