"""
Document Pipeline Worker — Extraction stage (US2 Sprint 3).

This is the composition root for Extraction jobs, dispatched by the OCR
worker (``workers.document_pipeline``) when the OCR stage completes. It
delegates to the Evidence context (create immutable ``EvidenceItem`` rows),
advances the Orchestrator's ``WorkflowStep``, and publishes ``EvidenceExtracted``
through the Transactional Outbox. It contains no business *rules* — no OCR
re-execution, no policy evaluation, and no finding generation. It performs job
pickup, execution dispatch, and result reporting only.

Responsibilities (and explicit non-responsibilities):
    - Resolves ``ExtractionProvider`` exclusively via ``ProviderRegistry``.
    - Loads the persisted ``OCRResultRecord`` (never re-runs OCR).
    - Executes extraction and persists ``EvidenceItem`` rows via
      ``EvidenceService`` (immutable, full provider-version attribution —
      Principle XII).
    - Emits the existing typed ``EvidenceExtracted`` ``DomainEvent`` through
      the Transactional Outbox (ADR-007) — never published directly to the bus.
    - Advances the ``WorkflowStep`` state (ADR-008 per-job Unit of Work).
    - Never generates Findings, never evaluates Policy, never invokes an
      ``InferenceProvider``.

Per-job Unit of Work (ADR-008): everything a job writes — the evidence items,
the audit events (synchronous, same transaction), the workflow step state, and
the outbox event — commits in the single transaction owned by
``workers.bootstrap.process_next``. A crash before commit leaves no partial
state; the redelivered job re-runs, and idempotency (the unique constraint on
``(document_id, extraction_model_version, evidence_type)``, checked via
``EvidenceRepository.exists_for_document_and_version``) makes the replay a
no-op.

Version pinning (ADR-009 / Principle XII): the workflow run pins the
extraction engine version at creation (``run.pinned_versions.extraction``).
This worker validates that the registered ``ExtractionProvider``'s live
``version()`` matches the pinned value before running — a mismatch is a
structural configuration drift, not a transient fault, and is therefore
terminal (non-retryable). The pinned/validated version is what gets recorded
as ``extraction_model_version`` on every ``EvidenceItem`` and as
``extraction_version`` on ``EvidenceExtracted``, never a value read fresh from
the provider at persistence time.

Provider resolution is exclusively through the DI container (``ProviderRegistry``).
Concrete provider classes are never imported or instantiated here.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

from mil.audit.writer import AuditWriter
from mil.document.ocr_repository import OCRResultRepository
from mil.evidence.repository import EvidenceRepository
from mil.evidence.service import EvidenceService
from mil.kernel.errors import NotFoundError, ProviderError, ProviderVersionMissingError
from mil.kernel.events import EvidenceExtracted, WorkflowStepFailed
from mil.kernel.metrics import MetricName
from mil.kernel.observability import MetricEmitter, NoOpMetricEmitter
from mil.kernel.providers.registry import ProviderRegistry
from mil.kernel.types import (
    ApplicationId,
    DocumentId,
    EvidenceItemId,
    TenantId,
    WorkflowRunId,
)
from mil.orchestrator.models import StepStatus, WorkflowRun, WorkflowStep
from mil.orchestrator.repository import WorkflowRepository
from mil.orchestrator.retry import (
    DeadLetterSink,
    NoOpDeadLetterSink,
    RetryDecision,
    RetryPolicy,
)
from mil.outbox.repository import OutboxRepository
from workers.bootstrap import build_worker_context, process_next

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from mil.kernel.container import Container
    from mil.kernel.job_queue import Job
    from mil.kernel.providers.extraction import ExtractionProvider
    from workers.bootstrap import JobHandler, WorkerContext

# Extraction step label dispatched by the OCR worker for the
# DOCUMENT_INGESTION workflow.
EXTRACTION_STEP_NAME = "EXTRACTION"

# Job type for every dispatched WorkflowStep job (orchestrator convention).
_JOB_TYPE_WORKFLOW_STEP = "workflow_step"


class ExtractionProcessingOutcome(enum.StrEnum):
    """
    Result of processing one Extraction job.

    COMPLETED       — extraction ran, EvidenceItems were persisted, the step
                      completed, and ``EvidenceExtracted`` was queued.
    ALREADY_DONE    — evidence already existed for (document, extraction
                      version); the job was a replay and was treated as a no-op.
    FAILED_TERMINAL — extraction failed permanently; the step is FAILED and
                      ``WorkflowStepFailed`` was queued.

    A retryable failure with attempts remaining does not produce an outcome — it
    propagates so the Unit of Work rolls back and the queue requeues the job.
    """

    COMPLETED = "COMPLETED"
    ALREADY_DONE = "ALREADY_DONE"
    FAILED_TERMINAL = "FAILED_TERMINAL"


@dataclass(frozen=True)
class ExtractionCollaborators:
    """Session-scoped collaborators for processing one Extraction job."""

    extraction_provider: ExtractionProvider
    ocr_results: OCRResultRepository
    evidence: EvidenceService
    evidence_items: EvidenceRepository
    workflows: WorkflowRepository
    outbox: OutboxRepository
    metrics: MetricEmitter = field(default_factory=NoOpMetricEmitter)


class ExtractionJobProcessor:
    """
    Coordinates a single Extraction job. Holds no business rules.

    Construct per job with session-scoped collaborators plus the retry policy
    and dead-letter sink (process-scoped extension points, ADR-008).
    """

    def __init__(
        self,
        collaborators: ExtractionCollaborators,
        *,
        retry_policy: RetryPolicy | None = None,
        dead_letter: DeadLetterSink | None = None,
    ) -> None:
        self._c = collaborators
        self._retry = retry_policy if retry_policy is not None else RetryPolicy()
        self._dead_letter = dead_letter if dead_letter is not None else NoOpDeadLetterSink()

    def process(self, job: Job) -> ExtractionProcessingOutcome:
        """
        Process one Extraction job end-to-end within the caller's transaction.

        Raises:
            NotFoundError: If the workflow run, step, or persisted OCR result
                is missing.
            ProviderError: Re-raised for a retryable failure with attempts
                remaining, so the Unit of Work rolls back and the job requeues.
        """
        document_id = _uuid(job.payload, "document_id")
        workflow_run_id = _uuid(job.payload, "workflow_run_id")
        step_name = str(job.payload.get("step_name", EXTRACTION_STEP_NAME))
        tenant_id = _uuid(job.payload, "tenant_id")
        application_id = _uuid(job.payload, "application_id")
        correlation_id = str(job.payload.get("correlation_id", ""))
        ocr_provider_version = str(job.payload.get("ocr_provider_version", ""))

        run = self._c.workflows.get_by_id(workflow_run_id)
        if run is None:
            raise NotFoundError("WorkflowRun", workflow_run_id)
        step = _find_step(run, step_name)
        if step is None:
            raise NotFoundError("WorkflowStep", step_name)

        # ADR-009 / Principle XII: validate the live provider matches the
        # version pinned to this run at creation — never trust the provider's
        # live version() output as the source of truth.
        expected_version = run.pinned_versions.extraction
        provider_version = self._c.extraction_provider.version()
        self._validate_provider_version(provider_version, expected_version)

        # Idempotent replay: evidence already extracted deterministically for
        # this (document, extraction version). Treat as a no-op (ADR-008).
        if self._c.evidence_items.exists_for_document_and_version(document_id, expected_version):
            if step.status != StepStatus.COMPLETED:
                step.mark_completed()
                self._c.workflows.save(run)
            return ExtractionProcessingOutcome.ALREADY_DONE

        ocr_record = self._c.ocr_results.get_by_document_and_version(
            document_id, ocr_provider_version
        )
        if ocr_record is None:
            raise NotFoundError("OCRResultRecord", f"{document_id}:{ocr_provider_version}")

        step.mark_in_progress()
        step.record_retry(job.retry_count)

        try:
            ocr_result = ocr_record.to_ocr_result()
            attrs_list = self._c.extraction_provider.extract_evidence(ocr_result, str(document_id))
            for attrs in attrs_list:
                self._validate_attrs_version(attrs.extraction_version, provider_version)
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

        # Success: persist immutable evidence items, complete the step, publish.
        created = self._c.evidence.create_evidence_items(
            application_id=application_id,
            document_id=document_id,
            workflow_run_id=workflow_run_id,
            tenant_id=tenant_id,
            attrs_list=attrs_list,
        )
        step.mark_completed()
        self._c.workflows.save(run)
        self._c.outbox.add(
            EvidenceExtracted(
                tenant_id=TenantId(tenant_id),
                document_id=DocumentId(document_id),
                application_id=ApplicationId(application_id),
                evidence_item_ids=tuple(EvidenceItemId(item.id) for item in created),
                extraction_version=expected_version,
                correlation_id=correlation_id,
            )
        )
        return ExtractionProcessingOutcome.COMPLETED

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
    ) -> ExtractionProcessingOutcome:
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
        return ExtractionProcessingOutcome.FAILED_TERMINAL

    @staticmethod
    def _validate_provider_version(reported_version: str, expected_version: str) -> None:
        """
        Enforce the pinned-version contract (ADR-009 / Principle XII).

        A missing or drifted provider version relative to the version pinned
        on the workflow run is a structural violation, not a transient fault —
        it is terminal (non-retryable).
        """
        if not reported_version:
            raise ProviderVersionMissingError("ExtractionProvider", "version")
        if reported_version != expected_version:
            raise ProviderError(
                f"ExtractionProvider version mismatch: registered provider reports "
                f"{reported_version!r}, workflow run pinned {expected_version!r}",
                provider_name="ExtractionProvider",
                retryable=False,
            )

    @staticmethod
    def _validate_attrs_version(attrs_version: str, expected_version: str) -> None:
        """
        Enforce that every returned ``EvidenceAttributes`` reports the same
        version as the provider's own ``version()`` — an internal consistency
        contract violation is terminal (non-retryable).
        """
        if not attrs_version:
            raise ProviderVersionMissingError("ExtractionProvider", "extraction_version")
        if attrs_version != expected_version:
            raise ProviderError(
                f"ExtractionProvider returned an EvidenceAttributes with extraction_version "
                f"{attrs_version!r}, expected {expected_version!r}",
                provider_name="ExtractionProvider",
                retryable=False,
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uuid(payload: dict[str, object], key: str) -> UUID:
    value = payload.get(key)
    if value is None:
        raise NotFoundError("ExtractionJobPayloadField", key)
    return UUID(str(value))


def _find_step(run: WorkflowRun, step_name: str) -> WorkflowStep | None:
    return next((s for s in run.steps if s.step_name == step_name), None)


# ---------------------------------------------------------------------------
# Wiring (composition root)
# ---------------------------------------------------------------------------


def build_extraction_collaborators(
    session: Session, container: Container
) -> ExtractionCollaborators:
    """
    Build the session-scoped collaborators for one Extraction job.

    Providers are resolved exclusively through the DI container's
    ``ProviderRegistry`` — concrete provider classes are never imported here.
    """
    registry = container.resolve(ProviderRegistry)
    extraction_provider = registry.get_extraction()
    metrics = container.resolve(MetricEmitter)  # type: ignore[type-abstract]

    audit = AuditWriter(session, metrics=metrics)
    evidence_repository = EvidenceRepository(session)
    evidence_service = EvidenceService(evidence_repository, audit)
    return ExtractionCollaborators(
        extraction_provider=extraction_provider,
        ocr_results=OCRResultRepository(session),
        evidence=evidence_service,
        evidence_items=evidence_repository,
        workflows=WorkflowRepository(session),
        outbox=OutboxRepository(session),
        metrics=metrics,
    )


def make_extraction_handler(
    container: Container,
    *,
    retry_policy: RetryPolicy | None = None,
    dead_letter: DeadLetterSink | None = None,
) -> JobHandler:
    """
    Build a ``JobHandler`` that processes Extraction jobs.

    The returned handler builds session-scoped collaborators per job and runs
    the ``ExtractionJobProcessor``. It does not commit — the bootstrap harness
    owns the transaction (per-job Unit of Work).
    """

    def handler(session: Session, job: Job) -> None:
        collaborators = build_extraction_collaborators(session, container)
        processor = ExtractionJobProcessor(
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
    """Entry point for the Extraction document-pipeline worker process."""
    ctx = build_worker_context()
    handler = make_extraction_handler(ctx.container)
    while True:
        if not process_next(ctx, handler):
            break


if __name__ == "__main__":  # pragma: no cover
    main()
