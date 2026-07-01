"""
Unit tests for workers.document_pipeline — the OCR worker.

The OCR coordination is exercised through ``OCRJobProcessor`` with in-memory
fakes (no database, no broker). Wiring (provider resolution via the DI
container) is tested separately.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from mil.document.models import Document, IngestionStatus
from mil.kernel.errors import NotFoundError, ProviderError, ProviderVersionMissingError
from mil.kernel.events import OCRCompleted, WorkflowStepFailed
from mil.kernel.job_queue import Job
from mil.kernel.providers.ocr import OCRResult, PageLayout, PageText
from mil.orchestrator.models import PinnedVersions, StepStatus, WorkflowRun, WorkflowStatus
from mil.orchestrator.retry import RetryPolicy  # noqa: TC001
from workers.document_pipeline import (
    OCR_STEP_NAME,
    OCRCollaborators,
    OCRJobProcessor,
    OCRProcessingOutcome,
)

_CONTENT = b"scanned document bytes"
_HASH = hashlib.sha256(_CONTENT).hexdigest()
_PROVIDER_VERSION = "mock-ocr-1.0.0"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _ocr_result(version: str = _PROVIDER_VERSION) -> OCRResult:
    return OCRResult(
        document_ref="ref",
        pages=(
            PageText(
                page_number=1,
                text="PAYSLIP",
                layout=PageLayout(page_number=1, width_points=595.0, height_points=842.0),
                word_count=1,
            ),
            PageText(
                page_number=2,
                text="TAX",
                layout=PageLayout(page_number=2, width_points=595.0, height_points=842.0),
                word_count=1,
            ),
        ),
        provider_version=version,
        processed_at=datetime.now(UTC),
    )


class FakeOCRProvider:
    def __init__(
        self,
        version: str = _PROVIDER_VERSION,
        *,
        result: OCRResult | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._version = version
        self._result = result if result is not None else _ocr_result(version)
        self._raises = raises
        self.calls = 0

    def process_document(self, document_ref: str, content: bytes) -> OCRResult:
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._result

    def version(self) -> str:
        return self._version


class FakeStorage:
    def __init__(self) -> None:
        self.retrieved: list[str] = []

    def retrieve(self, reference: str) -> bytes:
        self.retrieved.append(reference)
        return _CONTENT


class FakeOCRResultRepository:
    def __init__(self) -> None:
        self.saved: list[object] = []
        self._by_key: dict[tuple[UUID, str], object] = {}

    def save(self, record: object) -> None:
        self.saved.append(record)
        self._by_key[(record.document_id, record.provider_version)] = record  # type: ignore[attr-defined]

    def exists_for_document_and_version(self, document_id: UUID, provider_version: str) -> bool:
        return (document_id, provider_version) in self._by_key

    def seed(self, document_id: UUID, provider_version: str) -> None:
        self._by_key[(document_id, provider_version)] = object()


class FakeWorkflowRepository:
    def __init__(self, run: WorkflowRun) -> None:
        self._run = run
        self.save_count = 0

    def get_by_id(self, workflow_run_id: UUID) -> WorkflowRun | None:
        return self._run if workflow_run_id == self._run.id else None

    def save(self, run: WorkflowRun) -> None:
        self.save_count += 1


class FakeOutboxRepository:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, event: object) -> object:
        self.added.append(event)
        return event


class FakeDocumentService:
    def __init__(self, document: Document) -> None:
        self._document = document
        self.started: list[UUID] = []
        self.failed: list[tuple[UUID, str]] = []

    def start_processing(self, *, document_id: UUID) -> Document:
        self.started.append(document_id)
        if self._document.ingestion_status == IngestionStatus.PENDING:
            self._document.mark_processing()
        return self._document

    def fail_processing(self, *, document_id: UUID, reason: str) -> Document:
        self.failed.append((document_id, reason))
        if self._document.ingestion_status != IngestionStatus.FAILED:
            self._document.mark_failed(reason)
        return self._document


class SpyDeadLetterSink:
    def __init__(self) -> None:
        self.records: list[tuple[object, BaseException]] = []

    def record(self, job: object, error: BaseException) -> None:
        self.records.append((job, error))


class FakeJobQueue:
    def __init__(self) -> None:
        self.enqueued: list[Job] = []

    def enqueue(self, job: Job) -> None:
        self.enqueued.append(job)


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


def _make_document() -> Document:
    return Document.create(
        tenant_id=uuid4(),
        application_id=uuid4(),
        uploaded_by=uuid4(),
        original_filename="payslip.pdf",
        mime_type="application/pdf",
        size_bytes=len(_CONTENT),
        content_hash=_HASH,
        storage_reference="/tmp/mil/ref",
    )


def _make_run(application_id: UUID, tenant_id: UUID) -> WorkflowRun:
    run = WorkflowRun.create(
        tenant_id=tenant_id,
        application_id=application_id,
        workflow_type="DOCUMENT_INGESTION",
        idempotency_key=f"DOCUMENT_INGESTION:{uuid4()}",
        correlation_id="corr-ocr",
        pinned_versions=PinnedVersions(
            policy="1.0.0", extraction="e1", inference="m1", prompt="p1"
        ),
    )
    run.plan_step(step_name=OCR_STEP_NAME, step_order=0)
    run.mark_running()
    return run


class _Harness:
    def __init__(
        self,
        *,
        provider: FakeOCRProvider | None = None,
        retry_policy: RetryPolicy | None = None,
        dead_letter: SpyDeadLetterSink | None = None,
        correlation_id: str = "corr-ocr",
        retry_count: int = 0,
        max_retries: int = 3,
    ) -> None:
        self.document = _make_document()
        self.run = _make_run(self.document.application_id, self.document.tenant_id)
        self.run.correlation_id = correlation_id
        self.provider = provider if provider is not None else FakeOCRProvider()
        self.storage = FakeStorage()
        self.ocr_results = FakeOCRResultRepository()
        self.workflows = FakeWorkflowRepository(self.run)
        self.outbox = FakeOutboxRepository()
        self.documents = FakeDocumentService(self.document)
        self.job_queue = FakeJobQueue()
        self.dead_letter = dead_letter if dead_letter is not None else SpyDeadLetterSink()
        collaborators = OCRCollaborators(
            ocr_provider=self.provider,  # type: ignore[arg-type]
            storage=self.storage,  # type: ignore[arg-type]
            ocr_results=self.ocr_results,  # type: ignore[arg-type]
            workflows=self.workflows,  # type: ignore[arg-type]
            outbox=self.outbox,  # type: ignore[arg-type]
            documents=self.documents,  # type: ignore[arg-type]
            job_queue=self.job_queue,  # type: ignore[arg-type]
        )
        self.processor = OCRJobProcessor(
            collaborators, retry_policy=retry_policy, dead_letter=self.dead_letter
        )
        self.job = Job(
            job_type="workflow_step",
            idempotency_key=f"{self.run.id}:{OCR_STEP_NAME}",
            payload={
                "document_id": str(self.document.id),
                "workflow_run_id": str(self.run.id),
                "step_name": OCR_STEP_NAME,
                "application_id": str(self.document.application_id),
                "tenant_id": str(self.document.tenant_id),
                "correlation_id": correlation_id,
            },
            retry_count=retry_count,
            max_retries=max_retries,
        )

    @property
    def step(self) -> object:
        return self.run.steps[0]

    def run_processor(self) -> OCRProcessingOutcome:
        return self.processor.process(self.job)


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


class TestSuccess:
    def test_returns_completed(self) -> None:
        h = _Harness()
        assert h.run_processor() is OCRProcessingOutcome.COMPLETED

    def test_executes_ocr(self) -> None:
        h = _Harness()
        h.run_processor()
        assert h.provider.calls == 1

    def test_loads_document_via_storage(self) -> None:
        h = _Harness()
        h.run_processor()
        assert h.storage.retrieved == ["/tmp/mil/ref"]

    def test_persists_one_ocr_result(self) -> None:
        h = _Harness()
        h.run_processor()
        assert len(h.ocr_results.saved) == 1

    def test_ocr_result_records_provider_version(self) -> None:
        h = _Harness()
        h.run_processor()
        record = h.ocr_results.saved[0]
        assert record.provider_version == _PROVIDER_VERSION  # type: ignore[attr-defined]

    def test_marks_step_completed(self) -> None:
        h = _Harness()
        h.run_processor()
        assert h.step.status == StepStatus.COMPLETED  # type: ignore[attr-defined]

    def test_document_transitioned_to_in_progress(self) -> None:
        h = _Harness()
        h.run_processor()
        assert h.documents.started == [h.document.id]
        assert h.document.ingestion_status == IngestionStatus.IN_PROGRESS

    def test_emits_ocr_completed(self) -> None:
        h = _Harness()
        h.run_processor()
        assert len(h.outbox.added) == 1
        assert isinstance(h.outbox.added[0], OCRCompleted)

    def test_ocr_completed_has_provider_version_and_pages(self) -> None:
        h = _Harness()
        h.run_processor()
        event = h.outbox.added[0]
        assert isinstance(event, OCRCompleted)
        assert event.provider_version == _PROVIDER_VERSION
        assert event.page_count == 2

    def test_does_not_fail_document(self) -> None:
        h = _Harness()
        h.run_processor()
        assert h.documents.failed == []

    def test_no_next_step_dispatches_no_job(self) -> None:
        """A run with only an OCR step (no EXTRACTION step planned) is a no-op."""
        h = _Harness()
        h.run_processor()
        assert h.job_queue.enqueued == []


# ---------------------------------------------------------------------------
# Next-step dispatch (US2 Sprint 3 — Extraction stage)
# ---------------------------------------------------------------------------


class TestNextStepDispatch:
    def test_dispatches_extraction_job(self) -> None:
        h = _Harness()
        h.run.plan_step(step_name="EXTRACTION", step_order=1)
        h.run_processor()
        assert len(h.job_queue.enqueued) == 1
        job = h.job_queue.enqueued[0]
        assert job.job_type == "workflow_step"
        assert job.payload["step_name"] == "EXTRACTION"
        assert job.payload["document_id"] == str(h.document.id)
        assert job.payload["workflow_run_id"] == str(h.run.id)
        assert job.payload["ocr_provider_version"] == _PROVIDER_VERSION
        assert job.payload["page_count"] == 2

    def test_extraction_job_idempotency_key_is_deterministic(self) -> None:
        h = _Harness()
        h.run.plan_step(step_name="EXTRACTION", step_order=1)
        h.run_processor()
        job = h.job_queue.enqueued[0]
        assert job.idempotency_key == f"{h.run.id}:EXTRACTION"

    def test_terminal_failure_does_not_dispatch_next_step(self) -> None:
        h = _Harness(provider=FakeOCRProvider(raises=ProviderError("boom", retryable=False)))
        h.run.plan_step(step_name="EXTRACTION", step_order=1)
        h.run_processor()
        assert h.job_queue.enqueued == []


# ---------------------------------------------------------------------------
# Provider version validation (terminal)
# ---------------------------------------------------------------------------


class TestProviderVersionValidation:
    def test_missing_version_is_terminal(self) -> None:
        provider = FakeOCRProvider(result=_ocr_result(version=""))
        # version() must still report a value to drive the lookup/idempotency.
        provider._version = _PROVIDER_VERSION
        h = _Harness(provider=provider)
        assert h.run_processor() is OCRProcessingOutcome.FAILED_TERMINAL

    def test_version_mismatch_is_terminal(self) -> None:
        provider = FakeOCRProvider(version=_PROVIDER_VERSION, result=_ocr_result(version="other"))
        h = _Harness(provider=provider)
        assert h.run_processor() is OCRProcessingOutcome.FAILED_TERMINAL

    def test_mismatch_emits_workflow_step_failed(self) -> None:
        provider = FakeOCRProvider(version=_PROVIDER_VERSION, result=_ocr_result(version="other"))
        h = _Harness(provider=provider)
        h.run_processor()
        assert any(isinstance(e, WorkflowStepFailed) for e in h.outbox.added)


# ---------------------------------------------------------------------------
# Provider failure + retry behaviour
# ---------------------------------------------------------------------------


class TestRetryBehaviour:
    def test_retryable_with_attempts_remaining_propagates(self) -> None:
        provider = FakeOCRProvider(raises=ProviderError("temporary outage"))
        h = _Harness(provider=provider, retry_count=0, max_retries=3)
        with pytest.raises(ProviderError):
            h.run_processor()

    def test_retryable_propagation_records_no_terminal_state(self) -> None:
        provider = FakeOCRProvider(raises=ProviderError("temporary outage"))
        h = _Harness(provider=provider, retry_count=0, max_retries=3)
        with pytest.raises(ProviderError):
            h.run_processor()
        # No terminal failure recorded — the job will be requeued.
        assert h.documents.failed == []
        assert all(not isinstance(e, WorkflowStepFailed) for e in h.outbox.added)

    def test_retryable_exhausted_is_terminal(self) -> None:
        provider = FakeOCRProvider(raises=ProviderError("still down"))
        h = _Harness(provider=provider, retry_count=3, max_retries=3)
        assert h.run_processor() is OCRProcessingOutcome.FAILED_TERMINAL

    def test_retryable_exhausted_records_dead_letter(self) -> None:
        provider = FakeOCRProvider(raises=ProviderError("still down"))
        h = _Harness(provider=provider, retry_count=3, max_retries=3)
        h.run_processor()
        assert len(h.dead_letter.records) == 1

    def test_non_retryable_is_terminal_immediately(self) -> None:
        provider = FakeOCRProvider(raises=ProviderError("bad scan", retryable=False))
        h = _Harness(provider=provider, retry_count=0, max_retries=3)
        assert h.run_processor() is OCRProcessingOutcome.FAILED_TERMINAL

    def test_non_retryable_does_not_dead_letter(self) -> None:
        provider = FakeOCRProvider(raises=ProviderError("bad scan", retryable=False))
        h = _Harness(provider=provider, retry_count=0, max_retries=3)
        h.run_processor()
        assert h.dead_letter.records == []

    def test_version_missing_error_is_non_retryable_terminal(self) -> None:
        provider = FakeOCRProvider(
            raises=ProviderVersionMissingError("OCRProvider", "provider_version")
        )
        h = _Harness(provider=provider, retry_count=0, max_retries=3)
        assert h.run_processor() is OCRProcessingOutcome.FAILED_TERMINAL


# ---------------------------------------------------------------------------
# Terminal failure effects (workflow + document + outbox)
# ---------------------------------------------------------------------------


class TestTerminalFailure:
    def _terminal(self) -> _Harness:
        provider = FakeOCRProvider(raises=ProviderError("bad scan", retryable=False))
        h = _Harness(provider=provider)
        h.run_processor()
        return h

    def test_marks_step_failed(self) -> None:
        h = self._terminal()
        assert h.step.status == StepStatus.FAILED  # type: ignore[attr-defined]

    def test_records_error_on_step(self) -> None:
        h = self._terminal()
        assert h.step.error_message == "bad scan"  # type: ignore[attr-defined]

    def test_marks_run_failed(self) -> None:
        h = self._terminal()
        assert h.run.status == WorkflowStatus.FAILED

    def test_fails_document(self) -> None:
        h = self._terminal()
        assert h.documents.failed and h.document.ingestion_status == IngestionStatus.FAILED

    def test_emits_workflow_step_failed(self) -> None:
        h = self._terminal()
        assert any(isinstance(e, WorkflowStepFailed) for e in h.outbox.added)

    def test_emits_no_ocr_completed(self) -> None:
        h = self._terminal()
        assert all(not isinstance(e, OCRCompleted) for e in h.outbox.added)


# ---------------------------------------------------------------------------
# Idempotent replay
# ---------------------------------------------------------------------------


class TestIdempotentReplay:
    def test_existing_result_is_no_op(self) -> None:
        h = _Harness()
        h.ocr_results.seed(h.document.id, _PROVIDER_VERSION)
        assert h.run_processor() is OCRProcessingOutcome.ALREADY_DONE

    def test_replay_does_not_run_ocr(self) -> None:
        h = _Harness()
        h.ocr_results.seed(h.document.id, _PROVIDER_VERSION)
        h.run_processor()
        assert h.provider.calls == 0

    def test_replay_persists_no_new_result(self) -> None:
        h = _Harness()
        h.ocr_results.seed(h.document.id, _PROVIDER_VERSION)
        h.run_processor()
        assert h.ocr_results.saved == []

    def test_replay_emits_no_event(self) -> None:
        h = _Harness()
        h.ocr_results.seed(h.document.id, _PROVIDER_VERSION)
        h.run_processor()
        assert h.outbox.added == []


# ---------------------------------------------------------------------------
# Correlation propagation
# ---------------------------------------------------------------------------


class TestCorrelationPropagation:
    def test_ocr_completed_carries_correlation_id(self) -> None:
        h = _Harness(correlation_id="corr-xyz")
        h.run_processor()
        event = h.outbox.added[0]
        assert isinstance(event, OCRCompleted)
        assert event.correlation_id == "corr-xyz"

    def test_workflow_step_failed_carries_correlation_id(self) -> None:
        provider = FakeOCRProvider(raises=ProviderError("x", retryable=False))
        h = _Harness(provider=provider, correlation_id="corr-fail")
        h.run_processor()
        failed = next(e for e in h.outbox.added if isinstance(e, WorkflowStepFailed))
        assert failed.correlation_id == "corr-fail"


# ---------------------------------------------------------------------------
# Missing coordination state
# ---------------------------------------------------------------------------


class TestMissingState:
    def test_missing_run_raises(self) -> None:
        h = _Harness()
        h.job.payload["workflow_run_id"] = str(uuid4())  # unknown run
        with pytest.raises(NotFoundError):
            h.run_processor()

    def test_missing_document_id_raises(self) -> None:
        h = _Harness()
        del h.job.payload["document_id"]
        with pytest.raises(NotFoundError):
            h.run_processor()
