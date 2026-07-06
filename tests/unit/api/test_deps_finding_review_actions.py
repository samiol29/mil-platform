"""
Unit tests for ``mil.api.deps.FindingReviewActions`` — the verify/override/
escalate HTTP composition point.

Regression coverage for a real, previously-untested bug found via live
end-to-end testing: a brand-new ``ReviewSession`` is created in
``PENDING_REVIEW`` status, and the Review state machine only permits
``APPROVED``/``REJECTED``/``OVERRIDDEN`` from ``IN_REVIEW``
(``mil.review.models._VALID_TRANSITIONS``) — never directly from
``PENDING_REVIEW``. Nothing called the domain's own ``assign_reviewer``
before ``FindingReviewActions.verify``/``override`` were fixed to do so, so
verifying or overriding a fresh finding always raised
``InvalidStateTransitionError`` (surfaced to the API as a 422
``INVALID_STATE_TRANSITION``). These tests exercise the real
``FindingReviewActions``/``ReviewService``/``ReviewSession`` objects (not
mocks) so a regression in the state machine or the auto-assign wiring is
actually caught.
"""

from __future__ import annotations

from uuid import uuid4

from mil.api.deps import FindingReviewActions
from mil.kernel.security import AuthenticatedUser, Role
from mil.review.models import APPROVED, ESCALATED, IN_REVIEW, OVERRIDDEN, PENDING_REVIEW
from mil.review.models import ReviewSession as RealReviewSession
from mil.review.service import ReviewService


class FakeReviewRepository:
    def __init__(self) -> None:
        self.sessions: dict[object, RealReviewSession] = {}
        self.saved: list[RealReviewSession] = []
        self.actions: list[object] = []

    def get_session_for_finding(self, finding_id: object) -> RealReviewSession | None:
        return self.sessions.get(finding_id)

    def save_session(self, session: RealReviewSession) -> None:
        self.saved.append(session)

    def save_action(self, action: object) -> None:
        self.actions.append(action)

    def seed(self, session: RealReviewSession) -> None:
        self.sessions[session.finding_id] = session


class FakeAuditWriter:
    def record(self, **kwargs: object) -> object:
        return object()


def _make_session(*, status: str = PENDING_REVIEW) -> RealReviewSession:
    session = RealReviewSession.create(
        finding_id=uuid4(),
        application_id=uuid4(),
        tenant_id=uuid4(),
        workflow_run_id=uuid4(),
        policy_result_id=uuid4(),
    )
    if status != PENDING_REVIEW:
        session.transition_to(IN_REVIEW)
        if status != IN_REVIEW:
            session.transition_to(status)
    return session


def _make_actions(
    session_override: RealReviewSession,
) -> tuple[FindingReviewActions, FakeReviewRepository]:
    repo = FakeReviewRepository()
    repo.seed(session_override)
    actions = object.__new__(FindingReviewActions)
    actions._findings = None  # type: ignore[attr-defined]
    actions._reviews = repo  # type: ignore[attr-defined]
    actions._policy = None  # type: ignore[attr-defined]
    actions._review_service = ReviewService(repo, FakeAuditWriter())  # type: ignore[arg-type]
    return actions, repo


def _user(*roles: str) -> AuthenticatedUser:
    return AuthenticatedUser(user_id=uuid4(), tenant_id=uuid4(), roles=frozenset(roles))


class TestVerifyAutoAssignsFromPendingReview:
    def test_verify_succeeds_on_a_fresh_pending_review_session(self) -> None:
        """
        The exact bug: previously this raised InvalidStateTransitionError
        because nothing ever transitioned PENDING_REVIEW -> IN_REVIEW before
        ReviewService.approve_finding attempted PENDING_REVIEW -> APPROVED
        directly (not a valid edge in _VALID_TRANSITIONS).
        """
        session = _make_session(status=PENDING_REVIEW)
        actions, _ = _make_actions(session)
        result = actions.verify(_user(Role.UNDERWRITER), session.finding_id)
        assert result.status == APPROVED

    def test_verify_still_works_from_in_review(self) -> None:
        session = _make_session(status=IN_REVIEW)
        actions, _ = _make_actions(session)
        result = actions.verify(_user(Role.UNDERWRITER), session.finding_id)
        assert result.status == APPROVED

    def test_verify_still_works_from_escalated(self) -> None:
        session = _make_session(status=ESCALATED)
        actions, _ = _make_actions(session)
        result = actions.verify(_user(Role.UNDERWRITER), session.finding_id)
        assert result.status == APPROVED


class TestOverrideAutoAssignsFromPendingReview:
    def test_override_succeeds_on_a_fresh_pending_review_session(self) -> None:
        session = _make_session(status=PENDING_REVIEW)
        actions, _ = _make_actions(session)
        result = actions.override(
            _user(Role.UNDERWRITER),
            session.finding_id,
            reason="Income confirmed lower via payslip",
            previous_value="6500.00",
            new_value="6200.00",
        )
        assert result.status == OVERRIDDEN

    def test_override_still_works_from_in_review(self) -> None:
        session = _make_session(status=IN_REVIEW)
        actions, _ = _make_actions(session)
        result = actions.override(
            _user(Role.UNDERWRITER),
            session.finding_id,
            reason="Income confirmed lower via payslip",
            previous_value="6500.00",
            new_value="6200.00",
        )
        assert result.status == OVERRIDDEN


class TestEscalateUnaffectedByAutoAssign:
    def test_escalate_still_works_directly_from_pending_review(self) -> None:
        """
        PENDING_REVIEW -> ESCALATED is already a direct, valid edge — escalate
        must not be routed through the new auto-assign helper (which only
        ``verify``/``override`` call).
        """
        session = _make_session(status=PENDING_REVIEW)
        actions, _ = _make_actions(session)
        result = actions.escalate(
            _user(Role.UNDERWRITER),
            session.finding_id,
            reason="Needs compliance sign-off",
            target_role="COMPLIANCE_OFFICER",
        )
        assert result.status == ESCALATED
        assert result.assigned_reviewer_id is None
