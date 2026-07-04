"""
Unit tests for workers.extraction_pipeline — the Extraction worker.

The Extraction coordination is exercised through ``ExtractionJobProcessor``
with in-memory fakes (no database, no broker). Wiring (provider resolution via
the DI container) is tested separately.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from mil.document.ocr_models import OCRResultRecord
from mil.kernel.errors import NotFoundError, ProviderError, ProviderVersionMissingError
from mil.kernel.events import EvidenceExtracted, WorkflowStepFailed
from mil.kernel.job_queue import Job
from mil.kernel.providers.extraction import EvidenceAttributes, make_evidence_attributes
from mil.kernel.providers.ocr import OCRResult, PageLayout, PageText
from mil.orchestrator.models import PinnedVersions, StepStatus, WorkflowRun
from mil.orchestrator.retry import RetryPolicy  # noqa: TC001
from workers.extraction_pipeline import (
    EXTRACTION_STEP_NAME,
    ExtractionCollaborators,
    ExtractionJobProcessor,
    ExtractionProcessingOutcome,
)

_EXTRACTION_VERSION = "mock-extraction-1.0.0"
_OCR_PROVIDER_VERSION = "mock-ocr-1.0.0"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _ocr_result() -> OCRResult:
    return OCRResult(
        document_ref="ref",
        pages=(
            PageText(
                page_number=1,
                text="Gross Monthly Income: 5000.00",
                layout=PageLayout(page_number=1, width_points=595.0, height_points=842.0),
                word_count=4,
            ),
        ),
        provider_version=_OCR_PROVIDER_VERSION,
        processed_at=datetime.now(UTC),
    )


def _ocr_record(document_id: UUID, workflow_run_id: UUID, tenant_id: UUID) -> OCRResultRecord:
    return OCRResultRecord.create(
        document_id=document_id,
        workflow_run_id=workflow_run_id,
        tenant_id=tenant_id,
        ocr_result=_ocr_result(),
    )


def _one_attrs(version: str = _EXTRACTION_VERSION) -> EvidenceAttributes:
    return make_evidence_attributes(
        field_name="gross_monthly_income",
        field_value="5000.00",
        document_id="doc-1",
        source_document_ref="ref",
        page_number=1,
        field_location=None,
        extraction_confidence=0.85,
        extraction_method="mock-keyword-matcher",
        extraction_version=version,
        extracted_at=datetime.now(UTC),
    )


class FakeExtractionProvider:
    def __init__(
        self,
        version: str = _EXTRACTION_VERSION,
        *,
        results: list[EvidenceAttributes] | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._version = version
        # Defaults to a validly-versioned attrs list regardless of the
        # provider's own (possibly empty/drifted) version — the two are
        # deliberately decoupled so tests can exercise provider-version
        # validation without hitting EvidenceAttributes's own non-empty
        # extraction_version invariant.
        self._results = results if results is not None else [_one_attrs(_EXTRACTION_VERSION)]
        self._raises = raises
        self.calls = 0

    def extract_evidence(self, ocr_result: OCRResult, document_id: str) -> list[EvidenceAttributes]:
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._results

    def version(self) -> str:
        return self._version


class FakeOCRResultRepository:
    def __init__(self, record: OCRResultRecord | None) -> None:
        self._record = record

    def get_by_document_and_version(
        self, document_id: UUID, provider_version: str
    ) -> OCRResultRecord | None:
        return self._record


@dataclass
class _FakeCreatedItem:
    id: UUID = field(default_factory=uuid4)


class FakeEvidenceService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create_evidence_items(self, **kwargs: object) -> list[_FakeCreatedItem]:
        self.calls.append(kwargs)
        attrs_list = kwargs["attrs_list"]
        assert isinstance(attrs_list, list)
        return [_FakeCreatedItem() for _ in attrs_list]


class FakeEvidenceRepository:
    def __init__(self) -> None:
        self._existing: set[tuple[UUID, str]] = set()

    def exists_for_document_and_version(self, document_id: UUID, extraction_version: str) -> bool:
        return (document_id, extraction_version) in self._existing

    def seed(self, document_id: UUID, extraction_version: str) -> None:
        self._existing.add((document_id, extraction_version))


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
    def __init__(self) -> None:
        self.completed: list[tuple[UUID, int, int]] = []
        self.failed: list[tuple[UUID, str]] = []

    def complete_processing(
        self, *, document_id: UUID, page_count: int, evidence_item_count: int
    ) -> None:
        self.completed.append((document_id, page_count, evidence_item_count))

    def fail_processing(self, *, document_id: UUID, reason: str) -> None:
        self.failed.append((document_id, reason))


class SpyDeadLetterSink:
    def __init__(self) -> None:
        self.records: list[tuple[object, BaseException]] = []

    def record(self, job: object, error: BaseException) -> None:
        self.records.append((job, error))


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


def _make_run(application_id: UUID, tenant_id: UUID) -> WorkflowRun:
    run = WorkflowRun.create(
        tenant_id=tenant_id,
        application_id=application_id,
        workflow_type="DOCUMENT_INGESTION",
        idempotency_key=f"DOCUMENT_INGESTION:{uuid4()}",
        correlation_id="corr-extraction",
        pinned_versions=PinnedVersions(
            policy="1.0.0", extraction=_EXTRACTION_VERSION, inference="m1", prompt="p1"
        ),
    )
    run.plan_step(step_name="OCR", step_order=0)
    run.plan_step(step_name=EXTRACTION_STEP_NAME, step_order=1)
    run.mark_running()
    run.steps[0].mark_completed()
    return run


class _Harness:
    def __init__(
        self,
        *,
        provider: FakeExtractionProvider | None = None,
        ocr_record: OCRResultRecord | None | object = "__default__",
        retry_policy: RetryPolicy | None = None,
        dead_letter: SpyDeadLetterSink | None = None,
        correlation_id: str = "corr-extraction",
        retry_count: int = 0,
        max_retries: int = 3,
    ) -> None:
        self.document_id = uuid4()
        self.application_id = uuid4()
        self.tenant_id = uuid4()
        self.run = _make_run(self.application_id, self.tenant_id)
        self.run.correlation_id = correlation_id
        self.provider = provider if provider is not None else FakeExtractionProvider()
        resolved_ocr_record = (
            _ocr_record(self.document_id, self.run.id, self.tenant_id)
            if ocr_record == "__default__"
            else ocr_record
        )
        self.ocr_results = FakeOCRResultRepository(resolved_ocr_record)  # type: ignore[arg-type]
        self.evidence = FakeEvidenceService()
        self.evidence_items = FakeEvidenceRepository()
        self.documents = FakeDocumentService()
        self.workflows = FakeWorkflowRepository(self.run)
        self.outbox = FakeOutboxRepository()
        self.dead_letter = dead_letter if dead_letter is not None else SpyDeadLetterSink()
        collaborators = ExtractionCollaborators(
            extraction_provider=self.provider,  # type: ignore[arg-type]
            ocr_results=self.ocr_results,  # type: ignore[arg-type]
            evidence=self.evidence,  # type: ignore[arg-type]
            evidence_items=self.evidence_items,  # type: ignore[arg-type]
            documents=self.documents,  # type: ignore[arg-type]
            workflows=self.workflows,  # type: ignore[arg-type]
            outbox=self.outbox,  # type: ignore[arg-type]
        )
        self.processor = ExtractionJobProcessor(
            collaborators, retry_policy=retry_policy, dead_letter=self.dead_letter
        )
        self.job = Job(
            job_type="workflow_step",
            idempotency_key=f"{self.run.id}:{EXTRACTION_STEP_NAME}",
            payload={
                "document_id": str(self.document_id),
                "workflow_run_id": str(self.run.id),
                "step_name": EXTRACTION_STEP_NAME,
                "application_id": str(self.application_id),
                "tenant_id": str(self.tenant_id),
                "correlation_id": correlation_id,
                "ocr_provider_version": _OCR_PROVIDER_VERSION,
                "page_count": 1,
            },
            retry_count=retry_count,
            max_retries=max_retries,
        )

    @property
    def step(self) -> object:
        return self.run.steps[1]

    def run_processor(self) -> ExtractionProcessingOutcome:
        return self.processor.process(self.job)


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


class TestSuccess:
    def test_returns_completed(self) -> None:
        h = _Harness()
        assert h.run_processor() is ExtractionProcessingOutcome.COMPLETED

    def test_executes_extraction(self) -> None:
        h = _Harness()
        h.run_processor()
        assert h.provider.calls == 1

    def test_creates_evidence_items(self) -> None:
        h = _Harness()
        h.run_processor()
        assert len(h.evidence.calls) == 1
        assert len(h.evidence.calls[0]["attrs_list"]) == 1  # type: ignore[arg-type]

    def test_marks_step_completed(self) -> None:
        h = _Harness()
        h.run_processor()
        assert h.step.status == StepStatus.COMPLETED  # type: ignore[attr-defined]

    def test_completes_document_processing(self) -> None:
        """
        Extraction succeeding is what actually finishes the DOCUMENT_INGESTION
        workflow — DocumentService.complete_processing() must be invoked with
        the document's page count (from the persisted OCR result) and the
        number of EvidenceItems just created, or ingestion_status never
        advances past IN_PROGRESS.
        """
        h = _Harness()
        h.run_processor()
        assert h.documents.completed == [(h.document_id, 1, 1)]

    def test_emits_evidence_extracted(self) -> None:
        h = _Harness()
        h.run_processor()
        assert len(h.outbox.added) == 1
        assert isinstance(h.outbox.added[0], EvidenceExtracted)

    def test_evidence_extracted_carries_extraction_version(self) -> None:
        h = _Harness()
        h.run_processor()
        event = h.outbox.added[0]
        assert isinstance(event, EvidenceExtracted)
        assert event.extraction_version == _EXTRACTION_VERSION

    def test_evidence_extracted_carries_item_ids(self) -> None:
        h = _Harness()
        h.run_processor()
        event = h.outbox.added[0]
        assert isinstance(event, EvidenceExtracted)
        assert len(event.evidence_item_ids) == 1

    def test_multiple_attrs_create_multiple_items(self) -> None:
        provider = FakeExtractionProvider(results=[_one_attrs(), _one_attrs()])
        h = _Harness(provider=provider)
        h.run_processor()
        event = h.outbox.added[0]
        assert isinstance(event, EvidenceExtracted)
        assert len(event.evidence_item_ids) == 2


# ---------------------------------------------------------------------------
# Pinned-version validation (terminal — ADR-009 / Principle XII)
# ---------------------------------------------------------------------------


class TestPinnedVersionValidation:
    def test_missing_version_is_terminal(self) -> None:
        h = _Harness(provider=FakeExtractionProvider(version=""))
        with pytest.raises(ProviderVersionMissingError):
            h.run_processor()

    def test_mismatch_is_terminal(self) -> None:
        h = _Harness(provider=FakeExtractionProvider(version="drifted-version"))
        with pytest.raises(ProviderError) as exc_info:
            h.run_processor()
        assert exc_info.value.retryable is False

    def test_mismatch_does_not_touch_evidence(self) -> None:
        h = _Harness(provider=FakeExtractionProvider(version="drifted-version"))
        with pytest.raises(ProviderError):
            h.run_processor()
        assert h.evidence.calls == []

    def test_attrs_version_mismatch_is_terminal(self) -> None:
        """
        Unlike the provider-level version check (raised before any step state
        changes), a mismatch discovered per-attrs happens after work has begun
        and so is handled as a terminal step failure, not a raised exception.
        """
        mismatched = _one_attrs(version="something-else")
        h = _Harness(provider=FakeExtractionProvider(results=[mismatched]))
        assert h.run_processor() is ExtractionProcessingOutcome.FAILED_TERMINAL
        assert h.step.status == StepStatus.FAILED  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Idempotent replay
# ---------------------------------------------------------------------------


class TestIdempotentReplay:
    def test_existing_evidence_is_no_op(self) -> None:
        h = _Harness()
        h.evidence_items.seed(h.document_id, _EXTRACTION_VERSION)
        assert h.run_processor() is ExtractionProcessingOutcome.ALREADY_DONE

    def test_replay_does_not_run_extraction(self) -> None:
        h = _Harness()
        h.evidence_items.seed(h.document_id, _EXTRACTION_VERSION)
        h.run_processor()
        assert h.provider.calls == 0

    def test_replay_creates_no_new_evidence(self) -> None:
        h = _Harness()
        h.evidence_items.seed(h.document_id, _EXTRACTION_VERSION)
        h.run_processor()
        assert h.evidence.calls == []

    def test_replay_emits_no_event(self) -> None:
        h = _Harness()
        h.evidence_items.seed(h.document_id, _EXTRACTION_VERSION)
        h.run_processor()
        assert h.outbox.added == []

    def test_replay_marks_incomplete_step_completed(self) -> None:
        h = _Harness()
        h.evidence_items.seed(h.document_id, _EXTRACTION_VERSION)
        h.run_processor()
        assert h.step.status == StepStatus.COMPLETED  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Missing OCR result
# ---------------------------------------------------------------------------


class TestMissingOcrResult:
    def test_missing_ocr_record_raises_not_found(self) -> None:
        h = _Harness(ocr_record=None)
        with pytest.raises(NotFoundError):
            h.run_processor()


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------


class TestRetryBehaviour:
    def test_retryable_with_attempts_remaining_propagates(self) -> None:
        h = _Harness(
            provider=FakeExtractionProvider(raises=ProviderError("transient", retryable=True)),
            retry_count=0,
            max_retries=3,
        )
        with pytest.raises(ProviderError):
            h.run_processor()

    def test_retryable_exhausted_is_terminal(self) -> None:
        h = _Harness(
            provider=FakeExtractionProvider(raises=ProviderError("transient", retryable=True)),
            retry_count=3,
            max_retries=3,
        )
        assert h.run_processor() is ExtractionProcessingOutcome.FAILED_TERMINAL

    def test_retryable_exhausted_records_dead_letter(self) -> None:
        h = _Harness(
            provider=FakeExtractionProvider(raises=ProviderError("transient", retryable=True)),
            retry_count=3,
            max_retries=3,
        )
        h.run_processor()
        assert len(h.dead_letter.records) == 1

    def test_non_retryable_is_terminal_immediately(self) -> None:
        h = _Harness(
            provider=FakeExtractionProvider(raises=ProviderError("bad", retryable=False)),
            retry_count=0,
            max_retries=3,
        )
        assert h.run_processor() is ExtractionProcessingOutcome.FAILED_TERMINAL

    def test_non_retryable_does_not_dead_letter(self) -> None:
        h = _Harness(
            provider=FakeExtractionProvider(raises=ProviderError("bad", retryable=False)),
            retry_count=0,
            max_retries=3,
        )
        h.run_processor()
        assert h.dead_letter.records == []


# ---------------------------------------------------------------------------
# Terminal failure side effects
# ---------------------------------------------------------------------------


class TestTerminalFailure:
    def _run(self) -> _Harness:
        h = _Harness(provider=FakeExtractionProvider(raises=ProviderError("bad", retryable=False)))
        h.run_processor()
        return h

    def test_marks_step_failed(self) -> None:
        h = self._run()
        assert h.step.status == StepStatus.FAILED  # type: ignore[attr-defined]

    def test_marks_run_failed(self) -> None:
        h = self._run()
        assert h.run.status == "FAILED"

    def test_fails_document_processing(self) -> None:
        """
        A terminal Extraction failure must invoke DocumentService.fail_processing
        (previously missing entirely) or a permanently-failed document is left
        stuck IN_PROGRESS forever instead of transitioning to FAILED.
        """
        h = self._run()
        assert h.documents.failed == [(h.document_id, "bad")]

    def test_emits_workflow_step_failed(self) -> None:
        h = self._run()
        assert len(h.outbox.added) == 1
        assert isinstance(h.outbox.added[0], WorkflowStepFailed)

    def test_emits_no_evidence_extracted(self) -> None:
        h = self._run()
        assert not any(isinstance(e, EvidenceExtracted) for e in h.outbox.added)

    def test_creates_no_evidence(self) -> None:
        h = self._run()
        assert h.evidence.calls == []


# ---------------------------------------------------------------------------
# Correlation propagation
# ---------------------------------------------------------------------------


class TestCorrelationPropagation:
    def test_evidence_extracted_carries_correlation_id(self) -> None:
        h = _Harness(correlation_id="corr-xyz")
        h.run_processor()
        event = h.outbox.added[0]
        assert event.correlation_id == "corr-xyz"

    def test_workflow_step_failed_carries_correlation_id(self) -> None:
        h = _Harness(
            provider=FakeExtractionProvider(raises=ProviderError("bad", retryable=False)),
            correlation_id="corr-xyz",
        )
        h.run_processor()
        event = h.outbox.added[0]
        assert event.correlation_id == "corr-xyz"


# ---------------------------------------------------------------------------
# Missing coordination state
# ---------------------------------------------------------------------------


class TestMissingState:
    def test_missing_run_raises(self) -> None:
        h = _Harness()
        h.job.payload["workflow_run_id"] = str(uuid4())
        with pytest.raises(NotFoundError):
            h.run_processor()

    def test_missing_step_raises(self) -> None:
        h = _Harness()
        h.job.payload["step_name"] = "NONEXISTENT_STEP"
        with pytest.raises(NotFoundError):
            h.run_processor()

    def test_missing_document_id_raises(self) -> None:
        h = _Harness()
        del h.job.payload["document_id"]
        with pytest.raises(NotFoundError):
            h.run_processor()
