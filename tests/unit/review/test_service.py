"""Unit tests for mil.review.service — ReviewService."""

from __future__ import annotations

from uuid import uuid4

import pytest

from mil.kernel.errors import InvalidStateTransitionError, ValidationError
from mil.review.models import (
    ACTION_ESCALATED,
    ACTION_SESSION_STARTED,
    APPROVED,
    ESCALATED,
    IN_REVIEW,
    OVERRIDDEN,
    PENDING_REVIEW,
    REJECTED,
    ReviewAction,
    ReviewComment,
    ReviewSession,
)
from mil.review.service import ReviewService


class FakeReviewRepository:
    def __init__(self) -> None:
        self.saved_sessions: list[ReviewSession] = []
        self.saved_actions: list[ReviewAction] = []
        self.saved_comments: list[ReviewComment] = []

    def save_session(self, session: ReviewSession) -> None:
        self.saved_sessions.append(session)

    def create_session_if_not_exists(self, session: ReviewSession) -> bool:
        self.saved_sessions.append(session)
        return True

    def get_session_for_finding(self, finding_id: object) -> ReviewSession | None:
        return None

    def save_action(self, action: ReviewAction) -> None:
        self.saved_actions.append(action)

    def save_comment(self, comment: ReviewComment) -> None:
        self.saved_comments.append(comment)


class FakeAuditWriter:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record(self, **kwargs: object) -> object:
        self.records.append(kwargs)
        return object()


def _make_service() -> tuple[ReviewService, FakeReviewRepository, FakeAuditWriter]:
    repo = FakeReviewRepository()
    audit = FakeAuditWriter()
    return ReviewService(repo, audit), repo, audit  # type: ignore[arg-type]


def _start_review(service: ReviewService) -> ReviewSession:
    session, _created = service.start_review(
        finding_id=uuid4(),
        application_id=uuid4(),
        tenant_id=uuid4(),
        workflow_run_id=uuid4(),
        policy_result_id=uuid4(),
    )
    return session


# ---------------------------------------------------------------------------
# start_review
# ---------------------------------------------------------------------------


class TestStartReview:
    def test_creates_session_in_pending_review(self) -> None:
        service, repo, _ = _make_service()
        session = _start_review(service)
        assert session.status == PENDING_REVIEW
        assert session in repo.saved_sessions

    def test_records_session_started_action(self) -> None:
        service, repo, _ = _make_service()
        _start_review(service)
        assert len(repo.saved_actions) == 1
        assert repo.saved_actions[0].action_type == ACTION_SESSION_STARTED

    def test_session_started_action_has_no_human_actor(self) -> None:
        service, repo, _ = _make_service()
        _start_review(service)
        assert repo.saved_actions[0].actor_user_id is None
        assert repo.saved_actions[0].actor_type == "SYSTEM"

    def test_emits_review_session_started_audit_event(self) -> None:
        service, _, audit = _make_service()
        _start_review(service)
        assert audit.records[0]["event_type"] == "REVIEW_SESSION_STARTED"

    def test_links_session_to_finding_and_policy_result(self) -> None:
        service, repo, _ = _make_service()
        finding_id, policy_result_id = uuid4(), uuid4()
        service.start_review(
            finding_id=finding_id,
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            policy_result_id=policy_result_id,
        )
        assert repo.saved_sessions[0].finding_id == finding_id
        assert repo.saved_sessions[0].policy_result_id == policy_result_id

    def test_returns_created_true_on_first_call(self) -> None:
        service, _, _ = _make_service()
        _, created = service.start_review(
            finding_id=uuid4(),
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            policy_result_id=uuid4(),
        )
        assert created is True

    def test_replay_collision_returns_existing_session_without_duplicate_action_or_audit(
        self,
    ) -> None:
        """ADR-008 §5: a uniqueness collision on create is a no-op, not an error."""
        service, repo, audit = _make_service()
        existing = ReviewSession.create(
            finding_id=uuid4(),
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            policy_result_id=uuid4(),
        )
        repo.create_session_if_not_exists = lambda _session: False  # type: ignore[method-assign]
        repo.get_session_for_finding = lambda _finding_id: existing  # type: ignore[method-assign]

        session, created = service.start_review(
            finding_id=existing.finding_id,
            application_id=existing.application_id,
            tenant_id=existing.tenant_id,
            workflow_run_id=existing.workflow_run_id,
            policy_result_id=existing.policy_result_id,
        )

        assert created is False
        assert session is existing
        assert repo.saved_actions == []
        assert audit.records == []


# ---------------------------------------------------------------------------
# assign_reviewer
# ---------------------------------------------------------------------------


class TestAssignReviewer:
    def test_transitions_to_in_review(self) -> None:
        service, _, _ = _make_service()
        session = _start_review(service)
        reviewer_id = uuid4()
        service.assign_reviewer(session, reviewer_user_id=reviewer_id, assigned_by_user_id=uuid4())
        assert session.status == IN_REVIEW
        assert session.assigned_reviewer_id == reviewer_id

    def test_records_assigned_action_with_human_actor(self) -> None:
        service, repo, _ = _make_service()
        session = _start_review(service)
        assigner_id = uuid4()
        service.assign_reviewer(session, reviewer_user_id=uuid4(), assigned_by_user_id=assigner_id)
        action = repo.saved_actions[-1]
        assert action.actor_user_id == assigner_id
        assert action.actor_type == "USER"

    def test_emits_reviewer_assigned_audit_event(self) -> None:
        service, _, audit = _make_service()
        session = _start_review(service)
        service.assign_reviewer(session, reviewer_user_id=uuid4(), assigned_by_user_id=uuid4())
        assert audit.records[-1]["event_type"] == "REVIEW_REVIEWER_ASSIGNED"


# ---------------------------------------------------------------------------
# approve_finding
# ---------------------------------------------------------------------------


class TestApproveFinding:
    def test_transitions_to_approved(self) -> None:
        service, _, _ = _make_service()
        session = _start_review(service)
        service.assign_reviewer(session, reviewer_user_id=uuid4(), assigned_by_user_id=uuid4())
        service.approve_finding(session, actor_user_id=uuid4())
        assert session.status == APPROVED
        assert session.closed_at is not None

    def test_cannot_approve_without_being_in_review(self) -> None:
        service, _, _ = _make_service()
        session = _start_review(service)
        with pytest.raises(InvalidStateTransitionError):
            service.approve_finding(session, actor_user_id=uuid4())

    def test_emits_finding_approved_audit_event(self) -> None:
        service, _, audit = _make_service()
        session = _start_review(service)
        service.assign_reviewer(session, reviewer_user_id=uuid4(), assigned_by_user_id=uuid4())
        service.approve_finding(session, actor_user_id=uuid4())
        assert audit.records[-1]["event_type"] == "REVIEW_FINDING_APPROVED"

    def test_records_approved_action(self) -> None:
        service, repo, _ = _make_service()
        session = _start_review(service)
        service.assign_reviewer(session, reviewer_user_id=uuid4(), assigned_by_user_id=uuid4())
        service.approve_finding(session, actor_user_id=uuid4())
        assert repo.saved_actions[-1].new_status == APPROVED


# ---------------------------------------------------------------------------
# reject_finding
# ---------------------------------------------------------------------------


class TestRejectFinding:
    def test_transitions_to_rejected(self) -> None:
        service, _, _ = _make_service()
        session = _start_review(service)
        service.assign_reviewer(session, reviewer_user_id=uuid4(), assigned_by_user_id=uuid4())
        service.reject_finding(session, actor_user_id=uuid4(), reason="Insufficient evidence")
        assert session.status == REJECTED

    def test_requires_non_empty_reason(self) -> None:
        service, _, _ = _make_service()
        session = _start_review(service)
        service.assign_reviewer(session, reviewer_user_id=uuid4(), assigned_by_user_id=uuid4())
        with pytest.raises(ValidationError):
            service.reject_finding(session, actor_user_id=uuid4(), reason="")

    def test_records_reason_on_action(self) -> None:
        service, repo, _ = _make_service()
        session = _start_review(service)
        service.assign_reviewer(session, reviewer_user_id=uuid4(), assigned_by_user_id=uuid4())
        service.reject_finding(session, actor_user_id=uuid4(), reason="Not sufficient")
        assert repo.saved_actions[-1].reason == "Not sufficient"

    def test_emits_finding_rejected_audit_event(self) -> None:
        service, _, audit = _make_service()
        session = _start_review(service)
        service.assign_reviewer(session, reviewer_user_id=uuid4(), assigned_by_user_id=uuid4())
        service.reject_finding(session, actor_user_id=uuid4(), reason="Not sufficient")
        assert audit.records[-1]["event_type"] == "REVIEW_FINDING_REJECTED"


# ---------------------------------------------------------------------------
# override_finding (Principle I)
# ---------------------------------------------------------------------------


class TestOverrideFinding:
    def _in_review_session(self, service: ReviewService) -> ReviewSession:
        session = _start_review(service)
        service.assign_reviewer(session, reviewer_user_id=uuid4(), assigned_by_user_id=uuid4())
        return session

    def test_transitions_to_overridden(self) -> None:
        service, _, _ = _make_service()
        session = self._in_review_session(service)
        service.override_finding(
            session,
            actor_user_id=uuid4(),
            reason="Data entry error in source document",
            previous_value="FLAGGED: low confidence",
            new_value="Confirmed accurate after manual verification",
        )
        assert session.status == OVERRIDDEN
        assert session.closed_at is not None

    def test_requires_non_empty_reason(self) -> None:
        service, _, _ = _make_service()
        session = self._in_review_session(service)
        with pytest.raises(ValidationError):
            service.override_finding(
                session, actor_user_id=uuid4(), reason="", previous_value="a", new_value="b"
            )

    def test_requires_non_empty_new_value(self) -> None:
        service, _, _ = _make_service()
        session = self._in_review_session(service)
        with pytest.raises(ValidationError):
            service.override_finding(
                session, actor_user_id=uuid4(), reason="reason", previous_value="a", new_value=""
            )

    def test_records_full_attribution_on_action(self) -> None:
        """Principle I: reviewer, timestamp, reason, previous value, new decision."""
        service, repo, _ = _make_service()
        session = self._in_review_session(service)
        actor_id = uuid4()
        service.override_finding(
            session,
            actor_user_id=actor_id,
            reason="Data entry error",
            previous_value="FLAGGED",
            new_value="Corrected and accepted",
        )
        action = repo.saved_actions[-1]
        assert action.actor_user_id == actor_id
        assert action.created_at is not None
        assert action.reason == "Data entry error"
        assert action.previous_value == "FLAGGED"
        assert action.new_value == "Corrected and accepted"
        assert action.is_override is True

    def test_emits_finding_overridden_audit_event(self) -> None:
        service, _, audit = _make_service()
        session = self._in_review_session(service)
        service.override_finding(
            session,
            actor_user_id=uuid4(),
            reason="Data entry error",
            previous_value="FLAGGED",
            new_value="Corrected",
        )
        assert audit.records[-1]["event_type"] == "REVIEW_FINDING_OVERRIDDEN"

    def test_audit_event_carries_override_attribution(self) -> None:
        service, _, audit = _make_service()
        session = self._in_review_session(service)
        service.override_finding(
            session,
            actor_user_id=uuid4(),
            reason="Data entry error",
            previous_value="FLAGGED",
            new_value="Corrected",
        )
        event_data = audit.records[-1]["event_data"]
        assert event_data["reason"] == "Data entry error"  # type: ignore[index]
        assert event_data["previous_value"] == "FLAGGED"  # type: ignore[index]
        assert event_data["new_value"] == "Corrected"  # type: ignore[index]

    def test_cannot_override_without_being_in_review(self) -> None:
        service, _, _ = _make_service()
        session = _start_review(service)
        with pytest.raises(InvalidStateTransitionError):
            service.override_finding(
                session, actor_user_id=uuid4(), reason="r", previous_value="a", new_value="b"
            )


# ---------------------------------------------------------------------------
# escalate_finding
# ---------------------------------------------------------------------------


class TestEscalateFinding:
    def test_transitions_to_escalated(self) -> None:
        service, _, _ = _make_service()
        session = _start_review(service)
        service.escalate_finding(
            session,
            actor_user_id=uuid4(),
            reason="Possible fair-lending concern",
            target_role="COMPLIANCE_OFFICER",
        )
        assert session.status == ESCALATED

    def test_sets_target_role_on_session(self) -> None:
        service, _, _ = _make_service()
        session = _start_review(service)
        service.escalate_finding(
            session, actor_user_id=uuid4(), reason="reason", target_role="RISK_ANALYST"
        )
        assert session.escalated_to_role == "RISK_ANALYST"

    def test_sets_optional_target_user(self) -> None:
        service, _, _ = _make_service()
        session = _start_review(service)
        target_user_id = uuid4()
        service.escalate_finding(
            session,
            actor_user_id=uuid4(),
            reason="reason",
            target_role="UNDERWRITER",
            target_user_id=target_user_id,
        )
        assert session.escalated_to_user_id == target_user_id

    def test_saves_session_and_action(self) -> None:
        service, repo, _ = _make_service()
        session = _start_review(service)
        service.escalate_finding(
            session, actor_user_id=uuid4(), reason="reason", target_role="COMPLIANCE_OFFICER"
        )
        assert session in repo.saved_sessions
        assert repo.saved_actions[-1].action_type == ACTION_ESCALATED

    def test_action_records_target_role_and_reason(self) -> None:
        service, repo, _ = _make_service()
        session = _start_review(service)
        service.escalate_finding(
            session,
            actor_user_id=uuid4(),
            reason="Possible fair-lending concern",
            target_role="COMPLIANCE_OFFICER",
        )
        action = repo.saved_actions[-1]
        assert action.reason == "Possible fair-lending concern"
        assert action.target_role == "COMPLIANCE_OFFICER"

    def test_emits_escalated_audit_event(self) -> None:
        service, _, audit = _make_service()
        session = _start_review(service)
        service.escalate_finding(
            session, actor_user_id=uuid4(), reason="reason", target_role="COMPLIANCE_OFFICER"
        )
        assert audit.records[-1]["event_type"] == "REVIEW_FINDING_ESCALATED"

    def test_audit_event_includes_target_role(self) -> None:
        service, _, audit = _make_service()
        session = _start_review(service)
        service.escalate_finding(
            session, actor_user_id=uuid4(), reason="reason", target_role="RISK_ANALYST"
        )
        event_data = audit.records[-1]["event_data"]
        assert event_data["target_role"] == "RISK_ANALYST"  # type: ignore[index]

    def test_empty_reason_raises(self) -> None:
        service, _, _ = _make_service()
        session = _start_review(service)
        with pytest.raises(ValidationError):
            service.escalate_finding(
                session, actor_user_id=uuid4(), reason="", target_role="COMPLIANCE_OFFICER"
            )

    def test_empty_target_role_raises(self) -> None:
        service, _, _ = _make_service()
        session = _start_review(service)
        with pytest.raises(ValidationError):
            service.escalate_finding(
                session, actor_user_id=uuid4(), reason="reason", target_role=""
            )

    def test_can_escalate_directly_from_pending_review(self) -> None:
        service, _, _ = _make_service()
        session = _start_review(service)
        service.escalate_finding(
            session, actor_user_id=uuid4(), reason="reason", target_role="COMPLIANCE_OFFICER"
        )
        assert session.status == ESCALATED

    def test_escalated_finding_can_still_be_approved(self) -> None:
        service, _, _ = _make_service()
        session = _start_review(service)
        service.escalate_finding(
            session, actor_user_id=uuid4(), reason="reason", target_role="COMPLIANCE_OFFICER"
        )
        service.approve_finding(session, actor_user_id=uuid4())
        assert session.status == APPROVED

    def test_escalated_finding_can_be_re_escalated(self) -> None:
        service, repo, _ = _make_service()
        session = _start_review(service)
        service.escalate_finding(
            session, actor_user_id=uuid4(), reason="first reason", target_role="COMPLIANCE_OFFICER"
        )
        service.escalate_finding(
            session, actor_user_id=uuid4(), reason="second reason", target_role="RISK_ANALYST"
        )
        assert session.escalated_to_role == "RISK_ANALYST"
        assert len(repo.saved_actions) == 3  # SESSION_STARTED + two ESCALATED

    def test_cannot_escalate_a_terminal_session(self) -> None:
        service, _, _ = _make_service()
        session = _start_review(service)
        session.transition_to(IN_REVIEW)
        service.approve_finding(session, actor_user_id=uuid4())
        with pytest.raises(InvalidStateTransitionError):
            service.escalate_finding(
                session, actor_user_id=uuid4(), reason="reason", target_role="COMPLIANCE_OFFICER"
            )


# ---------------------------------------------------------------------------
# add_comment
# ---------------------------------------------------------------------------


class TestAddComment:
    def test_creates_comment(self) -> None:
        service, repo, _ = _make_service()
        session = _start_review(service)
        comment = service.add_comment(
            session, author_user_id=uuid4(), comment_text="Please verify the YTD figure."
        )
        assert comment in repo.saved_comments

    def test_emits_comment_added_audit_event(self) -> None:
        service, _, audit = _make_service()
        session = _start_review(service)
        service.add_comment(session, author_user_id=uuid4(), comment_text="Comment text")
        assert audit.records[-1]["event_type"] == "REVIEW_COMMENT_ADDED"
