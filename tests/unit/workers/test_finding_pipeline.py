"""
Unit tests for workers.finding_pipeline — the Finding worker and its
FINDING_GENERATION workflow trigger.

The Finding coordination is exercised through ``FindingJobProcessor`` with
in-memory fakes (no database, no broker). Wiring (provider resolution via the
DI container) is tested separately in ``test_finding_wiring.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from mil.kernel.errors import (
    NotFoundError,
    ProviderError,
    ProviderVersionMissingError,
    ValidationError,
)
from mil.kernel.events import FindingGenerated, WorkflowStepFailed
from mil.kernel.job_queue import Job
from mil.kernel.providers.inference import InferenceContext, InferenceResult
from mil.orchestrator.models import PinnedVersions, StepStatus, WorkflowRun, WorkflowStatus
from mil.orchestrator.retry import RetryPolicy  # noqa: TC001
from workers.finding_pipeline import (
    FINDING_STEP_NAME,
    FindingCollaborators,
    FindingJobProcessor,
    FindingProcessingOutcome,
)

_INFERENCE_VERSION = "mock-inference-1.0.0"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class _FakeEvidenceItem:
    evidence_type: str
    value_text: str
    extraction_confidence: Decimal
    id: UUID = field(default_factory=uuid4)
    document_id: UUID = field(default_factory=uuid4)
    page_number: int = 1


def _evidence_items() -> list[_FakeEvidenceItem]:
    return [
        _FakeEvidenceItem("gross_monthly_income", "5000.00", Decimal("0.850")),
        _FakeEvidenceItem("net_monthly_income", "4200.00", Decimal("0.950")),
    ]


def _inference_result(version: str = _INFERENCE_VERSION, **overrides: object) -> InferenceResult:
    defaults: dict[str, object] = {
        "content": "Evidence is consistent with the declared income.",
        "model_version": version,
        "prompt_version": "finding-generation-prompt-v1",
        "evidence_citations": (),
    }
    defaults.update(overrides)
    return InferenceResult(**defaults)  # type: ignore[arg-type]


@dataclass
class _FakeFinding:
    id: UUID = field(default_factory=uuid4)
    finding_type: str = "AI_GENERATED_ASSESSMENT"


class FakeInferenceProvider:
    def __init__(
        self,
        version: str = _INFERENCE_VERSION,
        *,
        result: InferenceResult | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._version = version
        self._result = result if result is not None else _inference_result(_INFERENCE_VERSION)
        self._raises = raises
        self.calls = 0

    def infer(self, context: InferenceContext) -> InferenceResult:
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._result

    def version(self) -> str:
        return self._version


class FakeEvidenceRepository:
    def __init__(self, items: list[_FakeEvidenceItem] | None = None) -> None:
        self._items = items if items is not None else _evidence_items()

    def get_for_application(self, application_id: UUID) -> list[_FakeEvidenceItem]:
        return self._items


class FakeFindingService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate_finding(self, **kwargs: object) -> _FakeFinding:
        self.calls.append(kwargs)
        return _FakeFinding()


class FakeFindingRepository:
    def __init__(self) -> None:
        self._existing: set[tuple[UUID, str]] = set()

    def exists_for_application_and_version(self, application_id: UUID, model_version: str) -> bool:
        return (application_id, model_version) in self._existing

    def seed(self, application_id: UUID, model_version: str) -> None:
        self._existing.add((application_id, model_version))


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


def _make_run(application_id: UUID, tenant_id: UUID) -> WorkflowRun:
    run = WorkflowRun.create(
        tenant_id=tenant_id,
        application_id=application_id,
        workflow_type="FINDING_GENERATION",
        idempotency_key=f"FINDING_GENERATION:{application_id}",
        correlation_id="corr-finding",
        pinned_versions=PinnedVersions(
            policy="n/a",
            extraction="mock-extraction-1.0.0",
            inference=_INFERENCE_VERSION,
            prompt="p1",
        ),
    )
    run.plan_step(step_name=FINDING_STEP_NAME, step_order=0)
    run.mark_running()
    return run


class _Harness:
    _UNSET: object = object()

    def __init__(
        self,
        *,
        provider: FakeInferenceProvider | None = None,
        evidence_items: list[_FakeEvidenceItem] | None | object = _UNSET,
        retry_policy: RetryPolicy | None = None,
        dead_letter: SpyDeadLetterSink | None = None,
        correlation_id: str = "corr-finding",
        retry_count: int = 0,
        max_retries: int = 3,
    ) -> None:
        self.application_id = uuid4()
        self.tenant_id = uuid4()
        self.run = _make_run(self.application_id, self.tenant_id)
        self.run.correlation_id = correlation_id
        self.provider = provider if provider is not None else FakeInferenceProvider()
        resolved_items = _evidence_items() if evidence_items is _Harness._UNSET else evidence_items
        self.evidence_items = FakeEvidenceRepository(resolved_items)  # type: ignore[arg-type]
        self.finding = FakeFindingService()
        self.findings = FakeFindingRepository()
        self.workflows = FakeWorkflowRepository(self.run)
        self.outbox = FakeOutboxRepository()
        self.job_queue = FakeJobQueue()
        self.dead_letter = dead_letter if dead_letter is not None else SpyDeadLetterSink()
        collaborators = FindingCollaborators(
            inference_provider=self.provider,  # type: ignore[arg-type]
            evidence_items=self.evidence_items,  # type: ignore[arg-type]
            finding=self.finding,  # type: ignore[arg-type]
            findings=self.findings,  # type: ignore[arg-type]
            workflows=self.workflows,  # type: ignore[arg-type]
            outbox=self.outbox,  # type: ignore[arg-type]
            job_queue=self.job_queue,  # type: ignore[arg-type]
        )
        self.processor = FindingJobProcessor(
            collaborators, retry_policy=retry_policy, dead_letter=self.dead_letter
        )
        self.job = Job(
            job_type="workflow_step",
            idempotency_key=f"{self.run.id}:{FINDING_STEP_NAME}",
            payload={
                "workflow_run_id": str(self.run.id),
                "step_name": FINDING_STEP_NAME,
                "application_id": str(self.application_id),
                "tenant_id": str(self.tenant_id),
                "correlation_id": correlation_id,
            },
            retry_count=retry_count,
            max_retries=max_retries,
        )

    @property
    def step(self) -> object:
        return self.run.steps[0]

    def run_processor(self) -> FindingProcessingOutcome:
        return self.processor.process(self.job)


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


class TestSuccess:
    def test_returns_completed(self) -> None:
        h = _Harness()
        assert h.run_processor() is FindingProcessingOutcome.COMPLETED

    def test_executes_inference(self) -> None:
        h = _Harness()
        h.run_processor()
        assert h.provider.calls == 1

    def test_generates_one_finding(self) -> None:
        h = _Harness()
        h.run_processor()
        assert len(h.finding.calls) == 1

    def test_finding_receives_all_evidence(self) -> None:
        h = _Harness()
        h.run_processor()
        assert len(h.finding.calls[0]["evidence_items"]) == 2  # type: ignore[arg-type]

    def test_finding_receives_pinned_extraction_version(self) -> None:
        h = _Harness()
        h.run_processor()
        assert h.finding.calls[0]["extraction_version"] == "mock-extraction-1.0.0"

    def test_marks_step_completed(self) -> None:
        h = _Harness()
        h.run_processor()
        assert h.step.status == StepStatus.COMPLETED  # type: ignore[attr-defined]

    def test_marks_run_completed_since_finding_is_sole_step(self) -> None:
        h = _Harness()
        h.run_processor()
        assert h.run.status == WorkflowStatus.COMPLETED

    def test_emits_finding_generated(self) -> None:
        h = _Harness()
        h.run_processor()
        assert len(h.outbox.added) == 1
        assert isinstance(h.outbox.added[0], FindingGenerated)

    def test_finding_generated_carries_pinned_policy_version(self) -> None:
        h = _Harness()
        h.run_processor()
        event = h.outbox.added[0]
        assert isinstance(event, FindingGenerated)
        assert event.policy_version == "n/a"

    def test_no_next_step_dispatches_no_job(self) -> None:
        """A run with only a FINDING step (no POLICY step planned) is a no-op."""
        h = _Harness()
        h.run_processor()
        assert h.job_queue.enqueued == []


# ---------------------------------------------------------------------------
# Next-step dispatch (US2 Sprint 5 — Policy Evaluation stage)
# ---------------------------------------------------------------------------


class TestNextStepDispatch:
    def test_dispatches_policy_job(self) -> None:
        h = _Harness()
        h.run.plan_step(step_name="POLICY", step_order=1)
        h.run_processor()
        assert len(h.job_queue.enqueued) == 1
        job = h.job_queue.enqueued[0]
        assert job.job_type == "workflow_step"
        assert job.payload["step_name"] == "POLICY"
        assert job.payload["application_id"] == str(h.application_id)
        assert job.payload["workflow_run_id"] == str(h.run.id)
        assert "finding_id" in job.payload

    def test_policy_job_idempotency_key_is_deterministic(self) -> None:
        h = _Harness()
        h.run.plan_step(step_name="POLICY", step_order=1)
        h.run_processor()
        job = h.job_queue.enqueued[0]
        assert job.idempotency_key == f"{h.run.id}:POLICY"

    def test_run_stays_running_when_policy_step_is_planned(self) -> None:
        """FINDING is no longer the last step, so the run must not complete yet."""
        h = _Harness()
        h.run.plan_step(step_name="POLICY", step_order=1)
        h.run_processor()
        assert h.run.status == WorkflowStatus.RUNNING

    def test_terminal_failure_does_not_dispatch_next_step(self) -> None:
        h = _Harness(provider=FakeInferenceProvider(raises=ProviderError("boom", retryable=False)))
        h.run.plan_step(step_name="POLICY", step_order=1)
        h.run_processor()
        assert h.job_queue.enqueued == []


# ---------------------------------------------------------------------------
# No evidence to evaluate
# ---------------------------------------------------------------------------


class TestNoEvidence:
    def test_empty_evidence_raises_validation_error(self) -> None:
        h = _Harness(evidence_items=[])
        with pytest.raises(ValidationError):
            h.run_processor()

    def test_empty_evidence_does_not_call_inference(self) -> None:
        h = _Harness(evidence_items=[])
        with pytest.raises(ValidationError):
            h.run_processor()
        assert h.provider.calls == 0


# ---------------------------------------------------------------------------
# Pinned-version validation (terminal — ADR-009 / Principle XII)
# ---------------------------------------------------------------------------


class TestPinnedVersionValidation:
    def test_missing_version_is_terminal(self) -> None:
        h = _Harness(provider=FakeInferenceProvider(version=""))
        with pytest.raises(ProviderVersionMissingError):
            h.run_processor()

    def test_mismatch_is_terminal(self) -> None:
        h = _Harness(provider=FakeInferenceProvider(version="drifted-version"))
        with pytest.raises(ProviderError) as exc_info:
            h.run_processor()
        assert exc_info.value.retryable is False

    def test_mismatch_does_not_generate_finding(self) -> None:
        h = _Harness(provider=FakeInferenceProvider(version="drifted-version"))
        with pytest.raises(ProviderError):
            h.run_processor()
        assert h.finding.calls == []

    def test_result_version_mismatch_is_terminal_outcome(self) -> None:
        mismatched = _inference_result(version="something-else")
        h = _Harness(provider=FakeInferenceProvider(result=mismatched))
        assert h.run_processor() is FindingProcessingOutcome.FAILED_TERMINAL
        assert h.step.status == StepStatus.FAILED  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Idempotent replay
# ---------------------------------------------------------------------------


class TestIdempotentReplay:
    def test_existing_finding_is_no_op(self) -> None:
        h = _Harness()
        h.findings.seed(h.application_id, _INFERENCE_VERSION)
        assert h.run_processor() is FindingProcessingOutcome.ALREADY_DONE

    def test_replay_does_not_run_inference(self) -> None:
        h = _Harness()
        h.findings.seed(h.application_id, _INFERENCE_VERSION)
        h.run_processor()
        assert h.provider.calls == 0

    def test_replay_generates_no_new_finding(self) -> None:
        h = _Harness()
        h.findings.seed(h.application_id, _INFERENCE_VERSION)
        h.run_processor()
        assert h.finding.calls == []

    def test_replay_emits_no_event(self) -> None:
        h = _Harness()
        h.findings.seed(h.application_id, _INFERENCE_VERSION)
        h.run_processor()
        assert h.outbox.added == []

    def test_replay_marks_incomplete_step_completed(self) -> None:
        h = _Harness()
        h.findings.seed(h.application_id, _INFERENCE_VERSION)
        h.run_processor()
        assert h.step.status == StepStatus.COMPLETED  # type: ignore[attr-defined]

    def test_replay_marks_run_completed(self) -> None:
        h = _Harness()
        h.findings.seed(h.application_id, _INFERENCE_VERSION)
        h.run_processor()
        assert h.run.status == WorkflowStatus.COMPLETED


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------


class TestRetryBehaviour:
    def test_retryable_with_attempts_remaining_propagates(self) -> None:
        h = _Harness(
            provider=FakeInferenceProvider(raises=ProviderError("transient", retryable=True)),
            retry_count=0,
            max_retries=3,
        )
        with pytest.raises(ProviderError):
            h.run_processor()

    def test_retryable_exhausted_is_terminal(self) -> None:
        h = _Harness(
            provider=FakeInferenceProvider(raises=ProviderError("transient", retryable=True)),
            retry_count=3,
            max_retries=3,
        )
        assert h.run_processor() is FindingProcessingOutcome.FAILED_TERMINAL

    def test_retryable_exhausted_records_dead_letter(self) -> None:
        h = _Harness(
            provider=FakeInferenceProvider(raises=ProviderError("transient", retryable=True)),
            retry_count=3,
            max_retries=3,
        )
        h.run_processor()
        assert len(h.dead_letter.records) == 1

    def test_non_retryable_is_terminal_immediately(self) -> None:
        h = _Harness(
            provider=FakeInferenceProvider(raises=ProviderError("bad", retryable=False)),
            retry_count=0,
            max_retries=3,
        )
        assert h.run_processor() is FindingProcessingOutcome.FAILED_TERMINAL

    def test_non_retryable_does_not_dead_letter(self) -> None:
        h = _Harness(
            provider=FakeInferenceProvider(raises=ProviderError("bad", retryable=False)),
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
        h = _Harness(provider=FakeInferenceProvider(raises=ProviderError("bad", retryable=False)))
        h.run_processor()
        return h

    def test_marks_step_failed(self) -> None:
        h = self._run()
        assert h.step.status == StepStatus.FAILED  # type: ignore[attr-defined]

    def test_marks_run_failed(self) -> None:
        h = self._run()
        assert h.run.status == "FAILED"

    def test_emits_workflow_step_failed(self) -> None:
        h = self._run()
        assert len(h.outbox.added) == 1
        assert isinstance(h.outbox.added[0], WorkflowStepFailed)

    def test_emits_no_finding_generated(self) -> None:
        h = self._run()
        assert not any(isinstance(e, FindingGenerated) for e in h.outbox.added)

    def test_generates_no_finding(self) -> None:
        h = self._run()
        assert h.finding.calls == []


# ---------------------------------------------------------------------------
# Correlation propagation
# ---------------------------------------------------------------------------


class TestCorrelationPropagation:
    def test_finding_generated_carries_correlation_id(self) -> None:
        h = _Harness(correlation_id="corr-xyz")
        h.run_processor()
        event = h.outbox.added[0]
        assert event.correlation_id == "corr-xyz"

    def test_workflow_step_failed_carries_correlation_id(self) -> None:
        h = _Harness(
            provider=FakeInferenceProvider(raises=ProviderError("bad", retryable=False)),
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

    def test_missing_application_id_raises(self) -> None:
        h = _Harness()
        del h.job.payload["application_id"]
        with pytest.raises(NotFoundError):
            h.run_processor()
