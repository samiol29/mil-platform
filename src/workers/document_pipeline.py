"""
Document Pipeline Worker — OCR stage (US2 Sprint 2).

This is the composition root for OCR jobs. Like ``api/deps.py`` for HTTP
requests, the worker is the one place permitted to wire several bounded contexts
together for a unit of work: it delegates the OCR-domain operations to the
Document context (run OCR, persist the immutable ``OCRResultRecord``, transition
the ``Document``), records the step outcome on the Orchestrator's
``WorkflowStep``, and publishes the result through the Transactional Outbox. It
contains no business *rules* — no policy, no evidence, no findings, no LLM
reasoning. It performs job pickup, execution dispatch, and result reporting only.

Per-job Unit of Work (ADR-008): everything a job writes — the document status,
the OCR result, the workflow step state, and the outbox event — commits in the
single transaction owned by ``workers.bootstrap.process_next``. A crash before
commit leaves no partial state; the redelivered job re-runs, and idempotency
(deterministic ``OCRResultRecord`` keyed by ``(document_id, provider_version)``)
makes the replay a no-op.

Document status is mutated only through ``DocumentService`` (ADR-006). The
orchestrator and this worker never write to the ``Document`` row directly.

Events are published only through the outbox (ADR-007): ``OCRCompleted`` on
success, ``WorkflowStepFailed`` on permanent failure. Never published directly
to the bus.

Provider resolution is exclusively through the DI container (``ProviderRegistry``).
Concrete provider classes are never imported or instantiated here.

On successful completion, this worker also dispatches the next planned
``WorkflowStep`` (the Extraction stage, US2 Sprint 3) as a job on the
``JobQueue``, carrying the OCR provider version and page count so the
Extraction worker can load the persisted ``OCRResultRecord`` without needing
the ``OCRProvider`` itself. If no further step is planned, dispatch is a no-op.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

from mil.audit.writer import AuditWriter
from mil.document.ocr_models import OCRResultRecord
from mil.document.ocr_repository import OCRResultRepository
from mil.document.repository import DocumentRepository
from mil.document.service import DocumentService
from mil.kernel.errors import NotFoundError, ProviderError, ProviderVersionMissingError
from mil.kernel.event_bus import EventBus
from mil.kernel.events import OCRCompleted, WorkflowStepFailed
from mil.kernel.job_queue import Job, JobQueue
from mil.kernel.metrics import MetricName
from mil.kernel.observability import MetricEmitter, NoOpMetricEmitter
from mil.kernel.providers.registry import ProviderRegistry
from mil.kernel.types import ApplicationId, DocumentId, TenantId, WorkflowRunId
from mil.orchestrator.models import PinnedVersions, StepStatus, WorkflowRun, WorkflowStep
from mil.orchestrator.repository import WorkflowRepository
from mil.orchestrator.retry import (
    DeadLetterSink,
    NoOpDeadLetterSink,
    RetryDecision,
    RetryPolicy,
)
from mil.orchestrator.service import IntelligenceOrchestrator
from mil.outbox.repository import OutboxRepository
from workers.bootstrap import build_worker_context, process_next, run_forever

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from mil.kernel.container import Container
    from mil.kernel.providers.ocr import OCRProvider, OCRResult
    from mil.kernel.providers.storage import StorageProvider
    from workers.bootstrap import JobHandler, WorkerContext

# OCR step label dispatched by the orchestrator for the DOCUMENT_INGESTION workflow.
OCR_STEP_NAME = "OCR"

# Mirrors workers.extraction_pipeline.EXTRACTION_STEP_NAME — duplicated as a
# literal (not imported) to avoid a cross-worker-module import; both workers
# already agree on this label via the orchestrator's planned step_names.
EXTRACTION_STEP_NAME = "EXTRACTION"

# Workflow type coordination label for the document ingestion pipeline
# (OCR -> EXTRACTION), mirrored from ARCHITECTURE.md / plan.md.
DOCUMENT_INGESTION_WORKFLOW_TYPE = "DOCUMENT_INGESTION"

# Sentinel for pinned-version dimensions that do not apply to this workflow
# type (ADR-009: a dimension that is genuinely not applicable is pinned to an
# explicit sentinel, never left blank).
_NOT_APPLICABLE_VERSION = "n/a"

# How long main()'s polling loop blocks on RedisJobQueue.dequeue() waiting for
# a job before checking again. A long-running worker process, not a one-shot
# drain — see main()'s docstring.
_POLL_TIMEOUT_SECONDS = 5.0


class OCRProcessingOutcome(enum.StrEnum):
    """
    Result of processing one OCR job.

    COMPLETED       — OCR ran, the result was persisted, the step completed,
                      and ``OCRCompleted`` was queued.
    ALREADY_DONE    — a result already existed for (document, provider version);
                      the job was a replay and was treated as a no-op.
    FAILED_TERMINAL — OCR failed permanently; the document and step are FAILED
                      and ``WorkflowStepFailed`` was queued.

    A retryable failure with attempts remaining does not produce an outcome — it
    propagates so the Unit of Work rolls back and the queue requeues the job.
    """

    COMPLETED = "COMPLETED"
    ALREADY_DONE = "ALREADY_DONE"
    FAILED_TERMINAL = "FAILED_TERMINAL"


@dataclass(frozen=True)
class OCRCollaborators:
    """Session-scoped collaborators for processing one OCR job."""

    ocr_provider: OCRProvider
    storage: StorageProvider
    ocr_results: OCRResultRepository
    workflows: WorkflowRepository
    outbox: OutboxRepository
    documents: DocumentService
    job_queue: JobQueue
    metrics: MetricEmitter = field(default_factory=NoOpMetricEmitter)


class OCRJobProcessor:
    """
    Coordinates a single OCR job. Holds no business rules.

    Construct per job with session-scoped collaborators plus the retry policy and
    dead-letter sink (process-scoped extension points, ADR-008).
    """

    def __init__(
        self,
        collaborators: OCRCollaborators,
        *,
        retry_policy: RetryPolicy | None = None,
        dead_letter: DeadLetterSink | None = None,
    ) -> None:
        self._c = collaborators
        self._retry = retry_policy if retry_policy is not None else RetryPolicy()
        self._dead_letter = dead_letter if dead_letter is not None else NoOpDeadLetterSink()

    def process(self, job: Job) -> OCRProcessingOutcome:
        """
        Process one OCR job end-to-end within the caller's transaction.

        Raises:
            NotFoundError: If the workflow run, step, or document is missing.
            ProviderError: Re-raised for a retryable failure with attempts
                remaining, so the Unit of Work rolls back and the job requeues.
        """
        document_id = _uuid(job.payload, "document_id")
        workflow_run_id = _uuid(job.payload, "workflow_run_id")
        step_name = str(job.payload.get("step_name", OCR_STEP_NAME))
        tenant_id = _uuid(job.payload, "tenant_id")
        application_id = _uuid(job.payload, "application_id")
        correlation_id = str(job.payload.get("correlation_id", ""))

        run = self._c.workflows.get_by_id(workflow_run_id)
        if run is None:
            raise NotFoundError("WorkflowRun", workflow_run_id)
        step = _find_step(run, step_name)
        if step is None:
            raise NotFoundError("WorkflowStep", step_name)

        provider_version = self._c.ocr_provider.version()

        # Idempotent replay: OCR already done deterministically for this
        # (document, provider version). Treat as a no-op (ADR-008).
        if self._c.ocr_results.exists_for_document_and_version(document_id, provider_version):
            if step.status != StepStatus.COMPLETED:
                step.mark_completed()
                self._c.workflows.save(run)
            return OCRProcessingOutcome.ALREADY_DONE

        step.mark_in_progress()
        step.record_retry(job.retry_count)
        document = self._c.documents.start_processing(document_id=document_id)

        try:
            content = self._c.storage.retrieve(document.storage_reference)
            result = self._c.ocr_provider.process_document(document.storage_reference, content)
            self._validate_version(result, provider_version)
        except ProviderError as exc:
            return self._handle_failure(
                run=run,
                step=step,
                document_id=document_id,
                tenant_id=tenant_id,
                workflow_run_id=workflow_run_id,
                correlation_id=correlation_id,
                job=job,
                exc=exc,
            )

        # Success: persist the immutable OCR result, complete the step, publish.
        record = OCRResultRecord.create(
            document_id=document_id,
            workflow_run_id=workflow_run_id,
            tenant_id=tenant_id,
            ocr_result=result,
        )
        if not self._c.ocr_results.save_if_not_exists(record):
            # Lost a race against another worker that committed first
            # (ADR-008 §5): treat exactly like the up-front replay check.
            if step.status != StepStatus.COMPLETED:
                step.mark_completed()
                self._c.workflows.save(run)
            return OCRProcessingOutcome.ALREADY_DONE
        step.mark_completed()
        self._c.workflows.save(run)
        self._c.outbox.add(
            OCRCompleted(
                tenant_id=TenantId(tenant_id),
                document_id=DocumentId(document_id),
                application_id=ApplicationId(application_id),
                workflow_run_id=WorkflowRunId(workflow_run_id),
                provider_version=provider_version,
                page_count=result.page_count,
                correlation_id=correlation_id,
            )
        )
        self._dispatch_next_step(
            run=run,
            completed_step=step,
            document_id=document_id,
            application_id=application_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            ocr_provider_version=provider_version,
            page_count=result.page_count,
        )
        self._c.metrics.increment(MetricName.OCR_JOBS_TOTAL)
        return OCRProcessingOutcome.COMPLETED

    def _dispatch_next_step(
        self,
        *,
        run: WorkflowRun,
        completed_step: WorkflowStep,
        document_id: UUID,
        application_id: UUID,
        tenant_id: UUID,
        correlation_id: str,
        ocr_provider_version: str,
        page_count: int,
    ) -> None:
        """
        Enqueue the job for the next planned step (the Extraction stage), if any.

        Mirrors ``IntelligenceOrchestrator.start_workflow``'s first-step
        dispatch: same job type, same idempotency-key derivation. A run with no
        further planned steps (e.g. OCR-only workflows in earlier sprints) is
        a no-op.
        """
        next_step = next(
            (s for s in run.steps if s.step_order == completed_step.step_order + 1), None
        )
        if next_step is None or next_step.status != StepStatus.PENDING:
            return
        self._c.job_queue.enqueue(
            Job(
                job_type=next_step.step_name,
                idempotency_key=f"{run.id}:{next_step.step_name}",
                payload={
                    "workflow_run_id": str(run.id),
                    "step_id": str(next_step.id),
                    "step_name": next_step.step_name,
                    "document_id": str(document_id),
                    "application_id": str(application_id),
                    "tenant_id": str(tenant_id),
                    "correlation_id": correlation_id,
                    "ocr_provider_version": ocr_provider_version,
                    "page_count": page_count,
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
        document_id: UUID,
        tenant_id: UUID,
        workflow_run_id: UUID,
        correlation_id: str,
        job: Job,
        exc: ProviderError,
    ) -> OCRProcessingOutcome:
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
        self._c.documents.fail_processing(document_id=document_id, reason=exc.message)
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
        return OCRProcessingOutcome.FAILED_TERMINAL

    @staticmethod
    def _validate_version(result: OCRResult, expected_version: str) -> None:
        """
        Enforce the provider version contract (Principle XII).

        A missing or mismatched version is a structural violation, not a
        transient fault — it is terminal (non-retryable).
        """
        if not result.provider_version:
            raise ProviderVersionMissingError("OCRProvider", "provider_version")
        if result.provider_version != expected_version:
            raise ProviderError(
                f"OCR provider version mismatch: result reported "
                f"{result.provider_version!r}, expected {expected_version!r}",
                provider_name="OCRProvider",
                retryable=False,
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uuid(payload: dict[str, object], key: str) -> UUID:
    value = payload.get(key)
    if value is None:
        raise NotFoundError("OCRJobPayloadField", key)
    return UUID(str(value))


def _find_step(run: WorkflowRun, step_name: str) -> WorkflowStep | None:
    return next((s for s in run.steps if s.step_name == step_name), None)


# ---------------------------------------------------------------------------
# Trigger (composition root for the document-upload -> pipeline-start point)
# ---------------------------------------------------------------------------


def start_document_ingestion_workflow(
    session: Session,
    container: Container,
    *,
    document_id: UUID,
    application_id: UUID,
    tenant_id: UUID,
    correlation_id: str | None = None,
) -> WorkflowRun:
    """
    Start (or return the existing) ``DOCUMENT_INGESTION`` workflow run for a
    single uploaded document.

    This is the trigger the API layer calls immediately after
    ``DocumentService.ingest_document`` persists a new ``Document`` — without
    it, an uploaded document is stored but never advances past PENDING, because
    nothing else in the platform starts the OCR -> Extraction pipeline
    (mirrors ``workers.finding_pipeline.start_finding_generation_workflow``,
    the equivalent trigger for the DRAFT -> SUBMITTED transition; see that
    function's docstring for the same rationale).

    Per ADR-009, only ``extraction`` is a meaningful pinned-version dimension
    for this workflow type (this run pins the extraction engine before the
    Extraction stage runs); ``policy``, ``inference``, and ``prompt`` are
    genuinely not applicable to document ingestion and are pinned to the
    explicit ``"n/a"`` sentinel rather than left blank.

    The caller is expected to invoke this within the same database transaction
    as the document's creation (the request's session), so the ``Document``
    row, the ``WorkflowRun``, its two planned steps (``OCR``, ``EXTRACTION``),
    and its ``WorkflowStarted`` outbox event all commit atomically (ADR-007 /
    ADR-008).

    Idempotent (ADR-008): the idempotency key is deterministic per document, so
    a repeat call (e.g. a retried request) returns the existing run rather than
    creating a duplicate or re-dispatching the first job.
    """
    registry = container.resolve(ProviderRegistry)
    extraction_version = registry.get_extraction().version()

    pinned = PinnedVersions(
        policy=_NOT_APPLICABLE_VERSION,
        extraction=extraction_version,
        inference=_NOT_APPLICABLE_VERSION,
        prompt=_NOT_APPLICABLE_VERSION,
    )

    orchestrator = IntelligenceOrchestrator(
        WorkflowRepository(session),
        OutboxRepository(session),
        container.resolve(JobQueue),
    )
    return orchestrator.start_workflow(
        tenant_id=tenant_id,
        application_id=application_id,
        workflow_type=DOCUMENT_INGESTION_WORKFLOW_TYPE,
        idempotency_key=f"{DOCUMENT_INGESTION_WORKFLOW_TYPE}:{document_id}",
        step_names=[OCR_STEP_NAME, EXTRACTION_STEP_NAME],
        pinned_versions=pinned,
        correlation_id=correlation_id,
        job_payload_extra={"document_id": str(document_id)},
    )


# ---------------------------------------------------------------------------
# Wiring (composition root)
# ---------------------------------------------------------------------------


def build_ocr_collaborators(session: Session, container: Container) -> OCRCollaborators:
    """
    Build the session-scoped collaborators for one OCR job.

    Providers are resolved exclusively through the DI container's
    ``ProviderRegistry`` — concrete provider classes are never imported here.
    """
    registry = container.resolve(ProviderRegistry)
    ocr_provider = registry.get_ocr()
    storage = registry.get_storage()
    event_bus = container.resolve(EventBus)  # type: ignore[type-abstract]
    job_queue = container.resolve(JobQueue)
    metrics = container.resolve(MetricEmitter)  # type: ignore[type-abstract]

    audit = AuditWriter(session, metrics=metrics)
    document_service = DocumentService(DocumentRepository(session, audit), storage, event_bus)
    return OCRCollaborators(
        ocr_provider=ocr_provider,
        storage=storage,
        ocr_results=OCRResultRepository(session),
        workflows=WorkflowRepository(session),
        outbox=OutboxRepository(session),
        documents=document_service,
        job_queue=job_queue,
        metrics=metrics,
    )


def make_ocr_handler(
    container: Container,
    *,
    retry_policy: RetryPolicy | None = None,
    dead_letter: DeadLetterSink | None = None,
) -> JobHandler:
    """
    Build a ``JobHandler`` that processes OCR jobs.

    The returned handler builds session-scoped collaborators per job and runs the
    ``OCRJobProcessor``. It does not commit — the bootstrap harness owns the
    transaction (per-job Unit of Work).
    """

    def handler(session: Session, job: Job) -> None:
        collaborators = build_ocr_collaborators(session, container)
        processor = OCRJobProcessor(
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
    """
    Entry point for the OCR document-pipeline worker process.

    Runs indefinitely as a long-running service via ``workers.bootstrap
    .run_forever``: each iteration blocks on ``RedisJobQueue.dequeue()`` for
    up to ``_POLL_TIMEOUT_SECONDS`` waiting for a job rather than exiting
    when the queue is momentarily empty (a worker process is expected to be
    started once and left running — the previous "process one batch then
    exit" loop meant a worker launched before any document had been uploaded
    would exit immediately and never see later work). ``run_forever`` also
    ensures one job's unhandled exception (a bad payload, a missing
    dependency, an unexpected bug) logs and moves on rather than killing this
    process and silently halting every other application's processing too —
    see its own docstring.
    """
    ctx = build_worker_context()
    handler = make_ocr_handler(ctx.container)
    run_forever(ctx, handler, job_type=OCR_STEP_NAME, poll_timeout=_POLL_TIMEOUT_SECONDS)


if __name__ == "__main__":  # pragma: no cover
    main()
