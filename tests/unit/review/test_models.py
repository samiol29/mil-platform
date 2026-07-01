"""Unit tests for mil.review.models — ReviewSession, ReviewAction, ReviewComment."""

from __future__ import annotations

from uuid import uuid4

import pytest

from mil.kernel.errors import InvalidStateTransitionError, ValidationError
from mil.review.models import (
    ACTION_APPROVED,
    ACTION_OVERRIDDEN,
    ACTION_SESSION_STARTED,
    APPROVED,
    IN_REVIEW,
    OVERRIDDEN,
    PENDING_REVIEW,
    REJECTED,
    ReviewAction,
    ReviewComment,
    ReviewSession,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(**overrides: object) -> ReviewSession:
    kwargs: dict[str, object] = {
        "finding_id": uuid4(),
        "application_id": uuid4(),
        "tenant_id": uuid4(),
        "workflow_run_id": uuid4(),
        "policy_result_id": uuid4(),
    }
    kwargs.update(overrides)
    return ReviewSession.create(**kwargs)  # type: ignore[arg-type]


def _make_action(**overrides: object) -> ReviewAction:
    kwargs: dict[str, object] = {
        "review_session_id": uuid4(),
        "action_type": ACTION_APPROVED,
        "previous_status": IN_REVIEW,
        "new_status": APPROVED,
        "actor_user_id": uuid4(),
    }
    kwargs.update(overrides)
    return ReviewAction.create(**kwargs)  # type: ignore[arg-type]


def _make_comment(**overrides: object) -> ReviewComment:
    kwargs: dict[str, object] = {
        "review_session_id": uuid4(),
        "author_user_id": uuid4(),
        "comment_text": "Looks consistent with payslip.",
    }
    kwargs.update(overrides)
    return ReviewComment.create(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ReviewSession.create
# ---------------------------------------------------------------------------


class TestReviewSessionCreate:
    def test_starts_pending_review(self) -> None:
        assert _make_session().status == PENDING_REVIEW

    def test_starts_unassigned(self) -> None:
        session = _make_session()
        assert session.assigned_reviewer_id is None
        assert session.assigned_at is None

    def test_starts_not_closed(self) -> None:
        assert _make_session().closed_at is None

    def test_sets_created_at_and_updated_at(self) -> None:
        session = _make_session()
        assert session.created_at is not None
        assert session.updated_at is not None

    def test_links_finding_application_run_and_policy_result(self) -> None:
        finding_id, app_id, run_id, result_id = uuid4(), uuid4(), uuid4(), uuid4()
        session = _make_session(
            finding_id=finding_id,
            application_id=app_id,
            workflow_run_id=run_id,
            policy_result_id=result_id,
        )
        assert session.finding_id == finding_id
        assert session.application_id == app_id
        assert session.workflow_run_id == run_id
        assert session.policy_result_id == result_id


# ---------------------------------------------------------------------------
# ReviewSession status transitions
# ---------------------------------------------------------------------------


class TestReviewSessionTransitions:
    def test_pending_to_in_review_allowed(self) -> None:
        session = _make_session()
        session.transition_to(IN_REVIEW)
        assert session.status == IN_REVIEW

    def test_in_review_to_approved_allowed(self) -> None:
        session = _make_session()
        session.transition_to(IN_REVIEW)
        session.transition_to(APPROVED)
        assert session.status == APPROVED

    def test_in_review_to_rejected_allowed(self) -> None:
        session = _make_session()
        session.transition_to(IN_REVIEW)
        session.transition_to(REJECTED)
        assert session.status == REJECTED

    def test_in_review_to_overridden_allowed(self) -> None:
        session = _make_session()
        session.transition_to(IN_REVIEW)
        session.transition_to(OVERRIDDEN)
        assert session.status == OVERRIDDEN

    def test_pending_directly_to_approved_rejected(self) -> None:
        session = _make_session()
        with pytest.raises(InvalidStateTransitionError):
            session.transition_to(APPROVED)

    def test_approved_is_terminal(self) -> None:
        session = _make_session()
        session.transition_to(IN_REVIEW)
        session.transition_to(APPROVED)
        with pytest.raises(InvalidStateTransitionError):
            session.transition_to(IN_REVIEW)

    def test_rejected_is_terminal(self) -> None:
        session = _make_session()
        session.transition_to(IN_REVIEW)
        session.transition_to(REJECTED)
        with pytest.raises(InvalidStateTransitionError):
            session.transition_to(APPROVED)

    def test_overridden_is_terminal(self) -> None:
        session = _make_session()
        session.transition_to(IN_REVIEW)
        session.transition_to(OVERRIDDEN)
        with pytest.raises(InvalidStateTransitionError):
            session.transition_to(APPROVED)

    def test_terminal_transition_sets_closed_at(self) -> None:
        session = _make_session()
        session.transition_to(IN_REVIEW)
        session.transition_to(APPROVED)
        assert session.closed_at is not None

    def test_non_terminal_transition_does_not_close(self) -> None:
        session = _make_session()
        session.transition_to(IN_REVIEW)
        assert session.closed_at is None

    def test_is_terminal_property(self) -> None:
        session = _make_session()
        assert session.is_terminal is False
        session.transition_to(IN_REVIEW)
        assert session.is_terminal is False
        session.transition_to(APPROVED)
        assert session.is_terminal is True


class TestAssignReviewer:
    def test_transitions_to_in_review(self) -> None:
        session = _make_session()
        reviewer_id = uuid4()
        session.assign_reviewer(reviewer_id)
        assert session.status == IN_REVIEW
        assert session.assigned_reviewer_id == reviewer_id
        assert session.assigned_at is not None

    def test_cannot_assign_twice(self) -> None:
        session = _make_session()
        session.assign_reviewer(uuid4())
        with pytest.raises(InvalidStateTransitionError):
            session.assign_reviewer(uuid4())


class TestReviewSessionOrmMetadata:
    def test_table_in_review_schema(self) -> None:
        assert ReviewSession.__table__.schema == "review"


# ---------------------------------------------------------------------------
# ReviewAction
# ---------------------------------------------------------------------------


class TestReviewActionCreate:
    def test_records_action_type(self) -> None:
        action = _make_action(action_type=ACTION_APPROVED)
        assert action.action_type == ACTION_APPROVED

    def test_records_actor_as_user_when_present(self) -> None:
        actor_id = uuid4()
        action = _make_action(actor_user_id=actor_id)
        assert action.actor_user_id == actor_id
        assert action.actor_type == "USER"

    def test_session_started_allows_no_actor(self) -> None:
        action = ReviewAction.create(
            review_session_id=uuid4(),
            action_type=ACTION_SESSION_STARTED,
            previous_status="",
            new_status=PENDING_REVIEW,
        )
        assert action.actor_user_id is None
        assert action.actor_type == "SYSTEM"

    def test_non_session_started_requires_actor(self) -> None:
        with pytest.raises(ValidationError):
            ReviewAction.create(
                review_session_id=uuid4(),
                action_type=ACTION_APPROVED,
                previous_status=IN_REVIEW,
                new_status=APPROVED,
                actor_user_id=None,
            )

    def test_empty_action_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make_action(action_type="")

    def test_records_reason_and_values_for_override(self) -> None:
        action = _make_action(
            action_type=ACTION_OVERRIDDEN,
            previous_status=IN_REVIEW,
            new_status=OVERRIDDEN,
            reason="Evidence shows a data-entry error in the payslip figure.",
            previous_value="FLAGGED",
            new_value="Corrected gross income accepted",
        )
        assert action.reason == "Evidence shows a data-entry error in the payslip figure."
        assert action.previous_value == "FLAGGED"
        assert action.new_value == "Corrected gross income accepted"

    def test_is_override_true_for_overridden_action(self) -> None:
        action = _make_action(action_type=ACTION_OVERRIDDEN, new_status=OVERRIDDEN)
        assert action.is_override is True

    def test_is_override_false_for_approved_action(self) -> None:
        action = _make_action(action_type=ACTION_APPROVED)
        assert action.is_override is False

    def test_sets_created_at(self) -> None:
        assert _make_action().created_at is not None

    def test_links_to_session(self) -> None:
        session_id = uuid4()
        action = _make_action(review_session_id=session_id)
        assert action.review_session_id == session_id


class TestReviewActionOrmMetadata:
    def test_table_in_review_schema(self) -> None:
        assert ReviewAction.__table__.schema == "review"


# ---------------------------------------------------------------------------
# ReviewComment
# ---------------------------------------------------------------------------


class TestReviewCommentCreate:
    def test_records_comment_text(self) -> None:
        comment = _make_comment(comment_text="Please double-check the YTD figure.")
        assert comment.comment_text == "Please double-check the YTD figure."

    def test_records_author(self) -> None:
        author_id = uuid4()
        comment = _make_comment(author_user_id=author_id)
        assert comment.author_user_id == author_id

    def test_empty_comment_text_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make_comment(comment_text="")

    def test_whitespace_only_comment_text_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make_comment(comment_text="   ")

    def test_sets_created_at(self) -> None:
        assert _make_comment().created_at is not None


class TestReviewCommentOrmMetadata:
    def test_table_in_review_schema(self) -> None:
        assert ReviewComment.__table__.schema == "review"
