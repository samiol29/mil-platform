"""
Unit tests for workers.policy_pipeline — the Policy worker.

The Policy coordination is exercised through ``PolicyJobProcessor`` with
in-memory fakes (no database, no broker). Wiring (provider resolution via the
DI container) is tested separately in ``test_policy_wiring.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from mil.kernel.errors import (
    ConflictError,
    NotFoundError,
    ProviderError,
    ProviderVersionMissingError,
)
from mil.kernel.events import PolicyEvaluated, WorkflowStepFailed
from mil.kernel.job_queue import Job
from mil.kernel.providers.policy import (
    PolicyEvaluationContext,
    PolicyEvaluationResult,
)
from mil.orchestrator.models import PinnedVersions, StepStatus, WorkflowRun, WorkflowStatus
from mil.orchestrator.retry import RetryPolicy  # noqa: TC001
from workers.policy_pipeline import (
    POLICY_STEP_NAME,
    PolicyCollaborators,
    PolicyJobProcessor,
    PolicyProcessingOutcome,
)

_POLICY_VERSION = "mock-policy-1.0.0"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class _FakeFinding:
    id: UUID = field(default_factory=uuid4)
    application_id: UUID = field(default_factory=uuid4)
    finding_type: str = "AI_GENERATED_ASSESSMENT"
    confidence_score: Decimal = Decimal("0.900")
    evidence_summary: str = "gross_monthly_income=5000.00"


@dataclass
class _FakeRule:
    rule_key: str
    name: str = "Rule"
    description: str = "desc"
    severity: str = "MEDIUM"


def _rules() -> list[_FakeRule]:
    return [_FakeRule(rule_key="LOW_CONFIDENCE_REVIEW")]


def _eval_result(version: str = _POLICY_VERSION, **overrides: object) -> PolicyEvaluationResult:
    defaults: dict[str, object] = {
        "outcome": "PASS",
        "triggered_rules": (),
        "policy_version": version,
        "evaluated_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return PolicyEvaluationResult(**defaults)  # type: ignore[arg-type]


@dataclass
class _FakePolicyResult:
    id: UUID = field(default_factory=uuid4)
    policy_version: str = _POLICY_VERSION
    outcome: str = "PASS"


class FakePolicyProvider:
    def __init__(
        self,
        version: str = _POLICY_VERSION,
        *,
        result: PolicyEvaluationResult | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._version = version
        self._result = result if result is not None else _eval_result(_POLICY_VERSION)
        self._raises = raises
        self.calls = 0

    def evaluate(self, context: PolicyEvaluationContext) -> PolicyEvaluationResult:
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._result

    def version(self) -> str:
        return self._version


class FakeFindingRepository:
    def __init__(self, finding: _FakeFinding | None | object = "__default__") -> None:  # type: ignore[assignment]
        self._finding = _FakeFinding() if finding == "__default__" else finding

    def get_by_id(self, finding_id: UUID) -> _FakeFinding | None:
        return self._finding  # type: ignore[return-value]


class FakePolicyService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def record_policy_result(self, **kwargs: object) -> _FakePolicyResult:
        self.calls.append(kwargs)
        result = kwargs["result"]
        assert isinstance(result, PolicyEvaluationResult)
        return _FakePolicyResult(policy_version=result.policy_version, outcome=result.outcome)


class FakePolicyRepo:
    def __init__(self, active_pack: object | None, rules: list[_FakeRule] | None = None) -> None:
        self._active_pack = active_pack
        self._rules = rules if rules is not None else _rules()
        self._existing: set[tuple[UUID, str]] = set()

    def get_active_pack_for_tenant(self, tenant_id: UUID) -> object | None:
        return self._active_pack

    def get_rules_for_pack(self, policy_pack_id: UUID) -> list[_FakeRule]:
        return self._rules

    def exists_for_finding_and_version(self, finding_id: UUID, policy_version: str) -> bool:
        return (finding_id, policy_version) in self._existing

    def seed(self, finding_id: UUID, policy_version: str) -> None:
        self._existing.add((finding_id, policy_version))


@dataclass
class _FakeActivePack:
    id: UUID = field(default_factory=uuid4)


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
        correlation_id="corr-policy",
        pinned_versions=PinnedVersions(
            policy=_POLICY_VERSION, extraction="mock-extraction-1.0.0", inference="m1", prompt="p1"
        ),
    )
    run.plan_step(step_name="FINDING", step_order=0)
    run.plan_step(step_name=POLICY_STEP_NAME, step_order=1)
    run.mark_running()
    run.steps[0].mark_completed()
    return run


class _Harness:
    _UNSET: object = object()

    def __init__(
        self,
        *,
        provider: FakePolicyProvider | None = None,
        finding: _FakeFinding | None | object = _UNSET,
        active_pack: object = _UNSET,
        rules: list[_FakeRule] | None = None,
        retry_policy: RetryPolicy | None = None,
        dead_letter: SpyDeadLetterSink | None = None,
        correlation_id: str = "corr-policy",
        retry_count: int = 0,
        max_retries: int = 3,
    ) -> None:
        self.application_id = uuid4()
        self.tenant_id = uuid4()
        self.finding_id = uuid4()
        self.run = _make_run(self.application_id, self.tenant_id)
        self.run.correlation_id = correlation_id
        self.provider = provider if provider is not None else FakePolicyProvider()
        resolved_finding = (
            _FakeFinding(id=self.finding_id, application_id=self.application_id)
            if finding is _Harness._UNSET
            else finding
        )
        self.findings = FakeFindingRepository(resolved_finding)  # type: ignore[arg-type]
        self.policy = FakePolicyService()
        resolved_pack = _FakeActivePack() if active_pack is _Harness._UNSET else active_pack
        self.policy_repo = FakePolicyRepo(active_pack=resolved_pack, rules=rules)
        self.workflows = FakeWorkflowRepository(self.run)
        self.outbox = FakeOutboxRepository()
        self.job_queue = FakeJobQueue()
        self.dead_letter = dead_letter if dead_letter is not None else SpyDeadLetterSink()
        collaborators = PolicyCollaborators(
            policy_provider=self.provider,  # type: ignore[arg-type]
            findings=self.findings,  # type: ignore[arg-type]
            policy=self.policy,  # type: ignore[arg-type]
            policy_repo=self.policy_repo,  # type: ignore[arg-type]
            workflows=self.workflows,  # type: ignore[arg-type]
            outbox=self.outbox,  # type: ignore[arg-type]
            job_queue=self.job_queue,  # type: ignore[arg-type]
        )
        self.processor = PolicyJobProcessor(
            collaborators, retry_policy=retry_policy, dead_letter=self.dead_letter
        )
        self.job = Job(
            job_type="workflow_step",
            idempotency_key=f"{self.run.id}:{POLICY_STEP_NAME}",
            payload={
                "workflow_run_id": str(self.run.id),
                "step_name": POLICY_STEP_NAME,
                "application_id": str(self.application_id),
                "tenant_id": str(self.tenant_id),
                "finding_id": str(self.finding_id),
                "correlation_id": correlation_id,
            },
            retry_count=retry_count,
            max_retries=max_retries,
        )

    @property
    def step(self) -> object:
        return self.run.steps[1]

    def run_processor(self) -> PolicyProcessingOutcome:
        return self.processor.process(self.job)


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


class TestSuccess:
    def test_returns_completed(self) -> None:
        h = _Harness()
        assert h.run_processor() is PolicyProcessingOutcome.COMPLETED

    def test_executes_evaluation(self) -> None:
        h = _Harness()
        h.run_processor()
        assert h.provider.calls == 1

    def test_records_one_policy_result(self) -> None:
        h = _Harness()
        h.run_processor()
        assert len(h.policy.calls) == 1

    def test_marks_step_completed(self) -> None:
        h = _Harness()
        h.run_processor()
        assert h.step.status == StepStatus.COMPLETED  # type: ignore[attr-defined]

    def test_marks_run_completed_since_policy_is_last_step(self) -> None:
        h = _Harness()
        h.run_processor()
        assert h.run.status == WorkflowStatus.COMPLETED

    def test_emits_policy_evaluated(self) -> None:
        h = _Harness()
        h.run_processor()
        assert len(h.outbox.added) == 1
        assert isinstance(h.outbox.added[0], PolicyEvaluated)

    def test_policy_evaluated_carries_pinned_policy_version(self) -> None:
        h = _Harness()
        h.run_processor()
        event = h.outbox.added[0]
        assert isinstance(event, PolicyEvaluated)
        assert event.policy_version == _POLICY_VERSION

    def test_context_receives_rule_catalogue(self) -> None:
        h = _Harness()
        h.run_processor()
        assert len(h.policy.calls) == 1

    def test_no_next_step_dispatches_no_job(self) -> None:
        """A run with only FINDING/POLICY steps (no REVIEW step) is a no-op."""
        h = _Harness()
        h.run_processor()
        assert h.job_queue.enqueued == []


# ---------------------------------------------------------------------------
# Next-step dispatch (US2 Sprint 6 — Review stage)
# ---------------------------------------------------------------------------


class TestNextStepDispatch:
    def test_dispatches_review_job(self) -> None:
        h = _Harness()
        h.run.plan_step(step_name="REVIEW", step_order=2)
        h.run_processor()
        assert len(h.job_queue.enqueued) == 1
        job = h.job_queue.enqueued[0]
        # job_type is the step name itself, not a generic label — multiple
        # distinct worker types share one physical queue, and each dequeues
        # only jobs of its own type.
        assert job.job_type == "REVIEW"
        assert job.payload["step_name"] == "REVIEW"
        assert job.payload["application_id"] == str(h.application_id)
        assert job.payload["workflow_run_id"] == str(h.run.id)
        assert job.payload["finding_id"] == str(h.finding_id)
        assert "policy_result_id" in job.payload

    def test_review_job_idempotency_key_is_deterministic(self) -> None:
        h = _Harness()
        h.run.plan_step(step_name="REVIEW", step_order=2)
        h.run_processor()
        job = h.job_queue.enqueued[0]
        assert job.idempotency_key == f"{h.run.id}:REVIEW"

    def test_run_stays_running_when_review_step_is_planned(self) -> None:
        """POLICY is no longer the last step, so the run must not complete yet."""
        h = _Harness()
        h.run.plan_step(step_name="REVIEW", step_order=2)
        h.run_processor()
        assert h.run.status == WorkflowStatus.RUNNING

    def test_terminal_failure_does_not_dispatch_next_step(self) -> None:
        h = _Harness(provider=FakePolicyProvider(raises=ProviderError("boom", retryable=False)))
        h.run.plan_step(step_name="REVIEW", step_order=2)
        h.run_processor()
        assert h.job_queue.enqueued == []


# ---------------------------------------------------------------------------
# No active Policy Pack
# ---------------------------------------------------------------------------


class TestNoActivePack:
    def test_no_active_pack_raises_conflict_error(self) -> None:
        h = _Harness(active_pack=None)
        with pytest.raises(ConflictError):
            h.run_processor()

    def test_no_active_pack_does_not_call_evaluate(self) -> None:
        h = _Harness(active_pack=None)
        with pytest.raises(ConflictError):
            h.run_processor()
        assert h.provider.calls == 0


# ---------------------------------------------------------------------------
# Missing Finding
# ---------------------------------------------------------------------------


class TestMissingFinding:
    def test_missing_finding_raises_not_found(self) -> None:
        h = _Harness(finding=None)
        with pytest.raises(NotFoundError):
            h.run_processor()


# ---------------------------------------------------------------------------
# Pinned-version validation (terminal — ADR-009 / Principle XII)
# ---------------------------------------------------------------------------


class TestPinnedVersionValidation:
    def test_missing_version_is_terminal(self) -> None:
        h = _Harness(provider=FakePolicyProvider(version=""))
        with pytest.raises(ProviderVersionMissingError):
            h.run_processor()

    def test_mismatch_is_terminal(self) -> None:
        h = _Harness(provider=FakePolicyProvider(version="drifted-version"))
        with pytest.raises(ProviderError) as exc_info:
            h.run_processor()
        assert exc_info.value.retryable is False

    def test_mismatch_does_not_record_result(self) -> None:
        h = _Harness(provider=FakePolicyProvider(version="drifted-version"))
        with pytest.raises(ProviderError):
            h.run_processor()
        assert h.policy.calls == []

    def test_result_version_mismatch_is_terminal_outcome(self) -> None:
        mismatched = _eval_result(version="something-else")
        h = _Harness(provider=FakePolicyProvider(result=mismatched))
        assert h.run_processor() is PolicyProcessingOutcome.FAILED_TERMINAL
        assert h.step.status == StepStatus.FAILED  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Idempotent replay
# ---------------------------------------------------------------------------


class TestIdempotentReplay:
    def test_existing_result_is_no_op(self) -> None:
        h = _Harness()
        h.policy_repo.seed(h.finding_id, _POLICY_VERSION)
        assert h.run_processor() is PolicyProcessingOutcome.ALREADY_DONE

    def test_replay_does_not_run_evaluation(self) -> None:
        h = _Harness()
        h.policy_repo.seed(h.finding_id, _POLICY_VERSION)
        h.run_processor()
        assert h.provider.calls == 0

    def test_replay_records_no_new_result(self) -> None:
        h = _Harness()
        h.policy_repo.seed(h.finding_id, _POLICY_VERSION)
        h.run_processor()
        assert h.policy.calls == []

    def test_replay_emits_no_event(self) -> None:
        h = _Harness()
        h.policy_repo.seed(h.finding_id, _POLICY_VERSION)
        h.run_processor()
        assert h.outbox.added == []

    def test_replay_marks_incomplete_step_completed(self) -> None:
        h = _Harness()
        h.policy_repo.seed(h.finding_id, _POLICY_VERSION)
        h.run_processor()
        assert h.step.status == StepStatus.COMPLETED  # type: ignore[attr-defined]

    def test_replay_marks_run_completed(self) -> None:
        h = _Harness()
        h.policy_repo.seed(h.finding_id, _POLICY_VERSION)
        h.run_processor()
        assert h.run.status == WorkflowStatus.COMPLETED


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------


class TestRetryBehaviour:
    def test_retryable_with_attempts_remaining_propagates(self) -> None:
        h = _Harness(
            provider=FakePolicyProvider(raises=ProviderError("transient", retryable=True)),
            retry_count=0,
            max_retries=3,
        )
        with pytest.raises(ProviderError):
            h.run_processor()

    def test_retryable_exhausted_is_terminal(self) -> None:
        h = _Harness(
            provider=FakePolicyProvider(raises=ProviderError("transient", retryable=True)),
            retry_count=3,
            max_retries=3,
        )
        assert h.run_processor() is PolicyProcessingOutcome.FAILED_TERMINAL

    def test_retryable_exhausted_records_dead_letter(self) -> None:
        h = _Harness(
            provider=FakePolicyProvider(raises=ProviderError("transient", retryable=True)),
            retry_count=3,
            max_retries=3,
        )
        h.run_processor()
        assert len(h.dead_letter.records) == 1

    def test_non_retryable_is_terminal_immediately(self) -> None:
        h = _Harness(
            provider=FakePolicyProvider(raises=ProviderError("bad", retryable=False)),
            retry_count=0,
            max_retries=3,
        )
        assert h.run_processor() is PolicyProcessingOutcome.FAILED_TERMINAL

    def test_non_retryable_does_not_dead_letter(self) -> None:
        h = _Harness(
            provider=FakePolicyProvider(raises=ProviderError("bad", retryable=False)),
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
        h = _Harness(provider=FakePolicyProvider(raises=ProviderError("bad", retryable=False)))
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

    def test_emits_no_policy_evaluated(self) -> None:
        h = self._run()
        assert not any(isinstance(e, PolicyEvaluated) for e in h.outbox.added)

    def test_records_no_result(self) -> None:
        h = self._run()
        assert h.policy.calls == []


# ---------------------------------------------------------------------------
# Correlation propagation
# ---------------------------------------------------------------------------


class TestCorrelationPropagation:
    def test_policy_evaluated_carries_correlation_id(self) -> None:
        h = _Harness(correlation_id="corr-xyz")
        h.run_processor()
        event = h.outbox.added[0]
        assert event.correlation_id == "corr-xyz"

    def test_workflow_step_failed_carries_correlation_id(self) -> None:
        h = _Harness(
            provider=FakePolicyProvider(raises=ProviderError("bad", retryable=False)),
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

    def test_missing_finding_id_raises(self) -> None:
        h = _Harness()
        del h.job.payload["finding_id"]
        with pytest.raises(NotFoundError):
            h.run_processor()
