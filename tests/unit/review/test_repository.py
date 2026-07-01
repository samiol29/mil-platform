"""Unit tests for mil.review.repository — ReviewRepository."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from mil.review.models import (
    ACTION_APPROVED,
    APPROVED,
    IN_REVIEW,
    ReviewAction,
    ReviewComment,
    ReviewSession,
)
from mil.review.repository import ReviewRepository


def _session() -> ReviewSession:
    return ReviewSession.create(
        finding_id=uuid4(),
        application_id=uuid4(),
        tenant_id=uuid4(),
        workflow_run_id=uuid4(),
        policy_result_id=uuid4(),
    )


def _action() -> ReviewAction:
    return ReviewAction.create(
        review_session_id=uuid4(),
        action_type=ACTION_APPROVED,
        previous_status=IN_REVIEW,
        new_status=APPROVED,
        actor_user_id=uuid4(),
    )


def _comment() -> ReviewComment:
    return ReviewComment.create(
        review_session_id=uuid4(), author_user_id=uuid4(), comment_text="Comment"
    )


def _make_repo() -> tuple[ReviewRepository, MagicMock]:
    session = MagicMock()
    return ReviewRepository(session), session


class TestSaveSession:
    def test_adds_and_flushes(self) -> None:
        repo, session = _make_repo()
        review_session = _session()
        repo.save_session(review_session)
        session.add.assert_called_once_with(review_session)
        session.flush.assert_called_once()


class TestGetSessionById:
    def test_returns_session(self) -> None:
        repo, session = _make_repo()
        review_session = _session()
        session.get.return_value = review_session
        assert repo.get_session_by_id(review_session.id) is review_session

    def test_returns_none_when_missing(self) -> None:
        repo, session = _make_repo()
        session.get.return_value = None
        assert repo.get_session_by_id(uuid4()) is None


class TestGetSessionForFinding:
    def test_returns_session(self) -> None:
        repo, session = _make_repo()
        review_session = _session()
        session.scalars.return_value.one_or_none.return_value = review_session
        assert repo.get_session_for_finding(uuid4()) is review_session

    def test_returns_none_when_absent(self) -> None:
        repo, session = _make_repo()
        session.scalars.return_value.one_or_none.return_value = None
        assert repo.get_session_for_finding(uuid4()) is None


class TestExistsForFinding:
    def test_true_when_present(self) -> None:
        repo, session = _make_repo()
        session.scalars.return_value.first.return_value = uuid4()
        assert repo.exists_for_finding(uuid4()) is True

    def test_false_when_absent(self) -> None:
        repo, session = _make_repo()
        session.scalars.return_value.first.return_value = None
        assert repo.exists_for_finding(uuid4()) is False


class TestGetPendingReviewsForTenant:
    def test_returns_list(self) -> None:
        repo, session = _make_repo()
        s1, s2 = _session(), _session()
        session.scalars.return_value = iter([s1, s2])
        assert repo.get_pending_reviews_for_tenant(uuid4()) == [s1, s2]


class TestSaveAction:
    def test_adds_and_flushes(self) -> None:
        repo, session = _make_repo()
        action = _action()
        repo.save_action(action)
        session.add.assert_called_once_with(action)
        session.flush.assert_called_once()

    def test_does_not_commit(self) -> None:
        repo, session = _make_repo()
        repo.save_action(_action())
        session.commit.assert_not_called()


class TestGetActionsForSession:
    def test_returns_list(self) -> None:
        repo, session = _make_repo()
        a1, a2 = _action(), _action()
        session.scalars.return_value = iter([a1, a2])
        assert repo.get_actions_for_session(uuid4()) == [a1, a2]


class TestSaveComment:
    def test_adds_and_flushes(self) -> None:
        repo, session = _make_repo()
        comment = _comment()
        repo.save_comment(comment)
        session.add.assert_called_once_with(comment)
        session.flush.assert_called_once()


class TestGetCommentsForSession:
    def test_returns_list(self) -> None:
        repo, session = _make_repo()
        c1, c2 = _comment(), _comment()
        session.scalars.return_value = iter([c1, c2])
        assert repo.get_comments_for_session(uuid4()) == [c1, c2]
