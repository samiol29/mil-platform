"""
Unit tests for workers.review_pipeline — the Review worker.

The Review coordination is exercised through ``ReviewJobProcessor`` with
in-memory fakes (no database, no broker). Wiring is tested separately in
``test_review_wiring.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from mil.kernel.errors import NotFoundError
from mil.kernel.events import ReviewCompleted, ReviewStarted, WorkflowCompleted
from mil.kernel.job_queue import Job
from mil.orchestrator.models import PinnedVersions, StepStatus, WorkflowRun, WorkflowStatus
from workers.review_pipeline import (
    REVIEW_STEP_NAME,
    ReviewCollaborators,
    ReviewJobProcessor,
    ReviewProcessingOutcome,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class _FakeReviewSession:
    id: UUID = field(default_factory=uuid4)
    status: str = "PENDING_REVIEW"


class FakeReviewService:
    def __init__(self, *, force_collision: bool = False) -> None:
        self.calls: list[dict[str, object]] = []
        self._force_collision = force_collision
        self._existing = _FakeReviewSession()

    def start_review(self, **kwargs: object) -> tuple[_FakeReviewSession, bool]:
        self.calls.append(kwargs)
        if self._force_collision:
            return self._existing, False
        return _FakeReviewSession(), True


class FakeReviewRepository:
    def __init__(self) -> None:
        self._existing: set[UUID] = set()

    def exists_for_finding(self, finding_id: UUID) -> bool:
        return finding_id in self._existing

    def seed(self, finding_id: UUID) -> None:
        self._existing.add(finding_id)


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


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


def _make_run(application_id: UUID, tenant_id: UUID) -> WorkflowRun:
    run = WorkflowRun.create(
        tenant_id=tenant_id,
        application_id=application_id,
        workflow_type="FINDING_GENERATION",
        idempotency_key=f"FINDING_GENERATION:{application_id}",
        correlation_id="corr-review",
        pinned_versions=PinnedVersions(
            policy="mock-policy-1.0.0",
            extraction="mock-extraction-1.0.0",
            inference="m1",
            prompt="p1",
        ),
    )
    run.plan_step(step_name="FINDING", step_order=0)
    run.plan_step(step_name="POLICY", step_order=1)
    run.plan_step(step_name=REVIEW_STEP_NAME, step_order=2)
    run.mark_running()
    run.steps[0].mark_completed()
    run.steps[1].mark_completed()
    return run


class _Harness:
    def __init__(self, *, correlation_id: str = "corr-review", retry_count: int = 0) -> None:
        self.application_id = uuid4()
        self.tenant_id = uuid4()
        self.finding_id = uuid4()
        self.policy_result_id = uuid4()
        self.run = _make_run(self.application_id, self.tenant_id)
        self.run.correlation_id = correlation_id
        self.review = FakeReviewService()
        self.reviews = FakeReviewRepository()
        self.workflows = FakeWorkflowRepository(self.run)
        self.outbox = FakeOutboxRepository()
        collaborators = ReviewCollaborators(
            review=self.review,  # type: ignore[arg-type]
            reviews=self.reviews,  # type: ignore[arg-type]
            workflows=self.workflows,  # type: ignore[arg-type]
            outbox=self.outbox,  # type: ignore[arg-type]
        )
        self.processor = ReviewJobProcessor(collaborators)
        self.job = Job(
            job_type="workflow_step",
            idempotency_key=f"{self.run.id}:{REVIEW_STEP_NAME}",
            payload={
                "workflow_run_id": str(self.run.id),
                "step_name": REVIEW_STEP_NAME,
                "application_id": str(self.application_id),
                "tenant_id": str(self.tenant_id),
                "finding_id": str(self.finding_id),
                "policy_result_id": str(self.policy_result_id),
                "correlation_id": correlation_id,
            },
            retry_count=retry_count,
        )

    @property
    def step(self) -> object:
        return self.run.steps[2]

    def run_processor(self) -> ReviewProcessingOutcome:
        return self.processor.process(self.job)


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


class TestSuccess:
    def test_returns_completed(self) -> None:
        h = _Harness()
        assert h.run_processor() is ReviewProcessingOutcome.COMPLETED

    def test_creates_one_review_session(self) -> None:
        h = _Harness()
        h.run_processor()
        assert len(h.review.calls) == 1

    def test_start_review_receives_finding_and_policy_result(self) -> None:
        h = _Harness()
        h.run_processor()
        call = h.review.calls[0]
        assert call["finding_id"] == h.finding_id
        assert call["policy_result_id"] == h.policy_result_id

    def test_marks_step_completed(self) -> None:
        h = _Harness()
        h.run_processor()
        assert h.step.status == StepStatus.COMPLETED  # type: ignore[attr-defined]

    def test_marks_run_completed_since_review_is_last_step(self) -> None:
        h = _Harness()
        h.run_processor()
        assert h.run.status == WorkflowStatus.COMPLETED

    def test_emits_review_started(self) -> None:
        h = _Harness()
        h.run_processor()
        assert any(isinstance(e, ReviewStarted) for e in h.outbox.added)

    def test_emits_review_completed(self) -> None:
        h = _Harness()
        h.run_processor()
        assert any(isinstance(e, ReviewCompleted) for e in h.outbox.added)

    def test_emits_workflow_completed_since_review_is_final_step(self) -> None:
        h = _Harness()
        h.run_processor()
        assert any(isinstance(e, WorkflowCompleted) for e in h.outbox.added)

    def test_emits_exactly_three_events(self) -> None:
        h = _Harness()
        h.run_processor()
        assert len(h.outbox.added) == 3

    def test_review_completed_status_reflects_pending_review(self) -> None:
        h = _Harness()
        h.run_processor()
        event = next(e for e in h.outbox.added if isinstance(e, ReviewCompleted))
        assert event.status == "PENDING_REVIEW"


# ---------------------------------------------------------------------------
# No further step planned (defensive — REVIEW is always last in this sprint)
# ---------------------------------------------------------------------------


class TestNotLastStep:
    def test_run_stays_running_when_more_steps_planned(self) -> None:
        h = _Harness()
        h.run.plan_step(step_name="FUTURE_STEP", step_order=3)
        h.run_processor()
        assert h.run.status == WorkflowStatus.RUNNING

    def test_no_workflow_completed_when_more_steps_planned(self) -> None:
        h = _Harness()
        h.run.plan_step(step_name="FUTURE_STEP", step_order=3)
        h.run_processor()
        assert not any(isinstance(e, WorkflowCompleted) for e in h.outbox.added)


# ---------------------------------------------------------------------------
# Idempotent replay
# ---------------------------------------------------------------------------


class TestIdempotentReplay:
    def test_existing_session_is_no_op(self) -> None:
        h = _Harness()
        h.reviews.seed(h.finding_id)
        assert h.run_processor() is ReviewProcessingOutcome.ALREADY_DONE

    def test_replay_does_not_create_session(self) -> None:
        h = _Harness()
        h.reviews.seed(h.finding_id)
        h.run_processor()
        assert h.review.calls == []

    def test_replay_emits_no_events(self) -> None:
        h = _Harness()
        h.reviews.seed(h.finding_id)
        h.run_processor()
        assert h.outbox.added == []

    def test_replay_marks_incomplete_step_completed(self) -> None:
        h = _Harness()
        h.reviews.seed(h.finding_id)
        h.run_processor()
        assert h.step.status == StepStatus.COMPLETED  # type: ignore[attr-defined]

    def test_replay_marks_run_completed(self) -> None:
        h = _Harness()
        h.reviews.seed(h.finding_id)
        h.run_processor()
        assert h.run.status == WorkflowStatus.COMPLETED


class TestConcurrentReplayCollision:
    """
    ADR-008 §5: the up-front `exists_for_finding` check (`TestIdempotentReplay`
    above) cannot close the race between two concurrent workers — both can
    pass it before either commits. A collision at insert time must still
    complete the step/run, but must not publish duplicate outbox events.
    """

    def test_returns_completed_not_an_exception(self) -> None:
        h = _Harness()
        h.review._force_collision = True
        assert h.run_processor() is ReviewProcessingOutcome.COMPLETED

    def test_emits_no_duplicate_event(self) -> None:
        h = _Harness()
        h.review._force_collision = True
        h.run_processor()
        assert h.outbox.added == []

    def test_marks_step_completed_despite_collision(self) -> None:
        h = _Harness()
        h.review._force_collision = True
        h.run_processor()
        assert h.step.status == StepStatus.COMPLETED  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Correlation propagation
# ---------------------------------------------------------------------------


class TestCorrelationPropagation:
    def test_events_carry_correlation_id(self) -> None:
        h = _Harness(correlation_id="corr-xyz")
        h.run_processor()
        for event in h.outbox.added:
            assert event.correlation_id == "corr-xyz"  # type: ignore[attr-defined]


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

    def test_missing_policy_result_id_raises(self) -> None:
        h = _Harness()
        del h.job.payload["policy_result_id"]
        with pytest.raises(NotFoundError):
            h.run_processor()
