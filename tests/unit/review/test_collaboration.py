"""Unit tests for Collaboration (spec 005-enterprise-platform §9):
ReviewComment's edit/soft-delete additions, and ReviewService's new
caller-checked comment methods."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from mil.kernel.errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from mil.kernel.security import AuthenticatedUser, Role
from mil.review.models import ReviewComment, ReviewSession
from mil.review.service import ReviewService


def _admin_caller(tenant_id: object, user_id: object | None = None) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id or uuid4(), tenant_id=tenant_id, roles=frozenset({Role.ADMIN})
    )


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


# ---------------------------------------------------------------------------
# ReviewComment model: edit / soft-delete
# ---------------------------------------------------------------------------


class TestReviewCommentEdit:
    def test_author_can_edit_within_window(self) -> None:
        author = uuid4()
        comment = ReviewComment.create(
            review_session_id=uuid4(), author_user_id=author, comment_text="original"
        )
        comment.edit(author, "revised")
        assert comment.comment_text == "revised"
        assert comment.edited_at is not None

    def test_non_author_cannot_edit(self) -> None:
        comment = ReviewComment.create(
            review_session_id=uuid4(), author_user_id=uuid4(), comment_text="original"
        )
        with pytest.raises(AuthorizationError):
            comment.edit(uuid4(), "revised")

    def test_edit_after_window_raises_conflict(self) -> None:
        author = uuid4()
        comment = ReviewComment.create(
            review_session_id=uuid4(), author_user_id=author, comment_text="original"
        )
        comment.created_at = datetime.now(UTC) - timedelta(minutes=10)
        with pytest.raises(ConflictError):
            comment.edit(author, "revised")

    def test_edit_rejects_empty_text(self) -> None:
        author = uuid4()
        comment = ReviewComment.create(
            review_session_id=uuid4(), author_user_id=author, comment_text="original"
        )
        with pytest.raises(ValidationError):
            comment.edit(author, "   ")


class TestReviewCommentSoftDelete:
    def test_author_can_delete(self) -> None:
        author = uuid4()
        comment = ReviewComment.create(
            review_session_id=uuid4(), author_user_id=author, comment_text="original"
        )
        comment.soft_delete(author)
        assert comment.is_deleted is True

    def test_non_author_cannot_delete(self) -> None:
        comment = ReviewComment.create(
            review_session_id=uuid4(), author_user_id=uuid4(), comment_text="original"
        )
        with pytest.raises(AuthorizationError):
            comment.soft_delete(uuid4())

    def test_delete_is_idempotent(self) -> None:
        author = uuid4()
        comment = ReviewComment.create(
            review_session_id=uuid4(), author_user_id=author, comment_text="original"
        )
        comment.soft_delete(author)
        comment.soft_delete(author)
        assert comment.is_deleted is True


# ---------------------------------------------------------------------------
# ReviewService: caller-checked collaboration methods
# ---------------------------------------------------------------------------


class FakeReviewRepository:
    def __init__(self) -> None:
        self.sessions_by_finding: dict[object, ReviewSession] = {}
        self.sessions_by_id: dict[object, ReviewSession] = {}
        self.comments: dict[object, ReviewComment] = {}
        self.escalated_query_args: dict[str, object] | None = None

    def seed_session(self, session: ReviewSession) -> None:
        self.sessions_by_finding[session.finding_id] = session
        self.sessions_by_id[session.id] = session

    def get_session_for_finding(self, finding_id: object) -> ReviewSession | None:
        return self.sessions_by_finding.get(finding_id)

    def get_session_by_id(self, session_id: object) -> ReviewSession | None:
        return self.sessions_by_id.get(session_id)

    def save_comment(self, comment: ReviewComment) -> None:
        self.comments[comment.id] = comment

    def get_comments_for_session(self, review_session_id: object) -> list[ReviewComment]:
        return [c for c in self.comments.values() if c.review_session_id == review_session_id]

    def get_comment_by_id(self, comment_id: object) -> ReviewComment | None:
        return self.comments.get(comment_id)

    def get_escalated_for_caller(
        self, tenant_id: object, *, roles: object, user_id: object
    ) -> list[ReviewSession]:
        self.escalated_query_args = {"tenant_id": tenant_id, "roles": roles, "user_id": user_id}
        return list(self.sessions_by_id.values())


class _FakeAuditEvent:
    def __init__(self) -> None:
        self.id = uuid4()


class FakeAuditWriter:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record(self, **kwargs: object) -> object:
        self.records.append(kwargs)
        return _FakeAuditEvent()


def _make_service() -> tuple[ReviewService, FakeReviewRepository, FakeAuditWriter]:
    repo = FakeReviewRepository()
    audit = FakeAuditWriter()
    return ReviewService(repo, audit), repo, audit  # type: ignore[arg-type]


class TestPostComment:
    def test_posts_comment_on_findings_review_session(self) -> None:
        service, repo, audit = _make_service()
        tenant_id = uuid4()
        session = _make_session(tenant_id=tenant_id)
        repo.seed_session(session)
        caller = _admin_caller(tenant_id)

        comment, _ = service.post_comment(caller, session.finding_id, comment_text="please review")

        assert comment.review_session_id == session.id
        assert audit.records[-1]["event_type"] == "REVIEW_COMMENT_ADDED"

    def test_no_review_session_yet_raises_not_found(self) -> None:
        service, _repo, _ = _make_service()
        caller = _admin_caller(uuid4())

        with pytest.raises(NotFoundError):
            service.post_comment(caller, uuid4(), comment_text="too early")

    def test_records_mentions(self) -> None:
        service, repo, audit = _make_service()
        tenant_id = uuid4()
        session = _make_session(tenant_id=tenant_id)
        repo.seed_session(session)
        caller = _admin_caller(tenant_id)
        mentioned = uuid4()

        comment, _ = service.post_comment(
            caller, session.finding_id, comment_text="cc", mentioned_user_ids=[mentioned]
        )

        assert comment.mentioned_user_ids == [str(mentioned)]
        assert audit.records[-1]["event_data"]["mentioned_user_ids"] == [str(mentioned)]


class TestGetCommentsForFinding:
    def test_returns_comments_for_the_findings_session_only(self) -> None:
        service, repo, _ = _make_service()
        tenant_id = uuid4()
        session_a = _make_session(tenant_id=tenant_id)
        session_b = _make_session(tenant_id=tenant_id)
        repo.seed_session(session_a)
        repo.seed_session(session_b)
        caller = _admin_caller(tenant_id)

        service.post_comment(caller, session_a.finding_id, comment_text="on A")
        service.post_comment(caller, session_b.finding_id, comment_text="on B")

        comments_a = service.get_comments_for_finding(caller, session_a.finding_id)
        assert len(comments_a) == 1
        assert comments_a[0].comment_text == "on A"


class TestEditAndDeleteComment:
    def test_author_can_edit_via_service(self) -> None:
        service, repo, _ = _make_service()
        tenant_id = uuid4()
        session = _make_session(tenant_id=tenant_id)
        repo.seed_session(session)
        author_id = uuid4()
        caller = _admin_caller(tenant_id, author_id)
        comment, _ = service.post_comment(caller, session.finding_id, comment_text="v1")

        edited = service.edit_comment(caller, comment, "v2")

        assert edited.comment_text == "v2"

    def test_get_comment_scopes_by_tenant(self) -> None:
        service, repo, _ = _make_service()
        tenant_a = uuid4()
        session = _make_session(tenant_id=tenant_a)
        repo.seed_session(session)
        caller_a = _admin_caller(tenant_a)
        comment, _ = service.post_comment(caller_a, session.finding_id, comment_text="v1")

        caller_b = _admin_caller(uuid4())
        with pytest.raises(NotFoundError):
            service.get_comment(caller_b, comment.id)

    def test_delete_via_service(self) -> None:
        service, repo, _ = _make_service()
        tenant_id = uuid4()
        session = _make_session(tenant_id=tenant_id)
        repo.seed_session(session)
        author_id = uuid4()
        caller = _admin_caller(tenant_id, author_id)
        comment, _ = service.post_comment(caller, session.finding_id, comment_text="v1")

        deleted = service.delete_comment(caller, comment)

        assert deleted.is_deleted is True


class TestGetEscalatedForCaller:
    """Final product polish sprint (A5): the escalation queue."""

    def test_passes_callers_tenant_roles_and_user_id(self) -> None:
        service, repo, _ = _make_service()
        tenant_id = uuid4()
        caller = AuthenticatedUser(
            user_id=uuid4(), tenant_id=tenant_id, roles=frozenset({Role.RISK_ANALYST})
        )
        service.get_escalated_for_caller(caller)
        assert repo.escalated_query_args == {
            "tenant_id": tenant_id,
            "roles": caller.roles,
            "user_id": caller.user_id,
        }

    def test_returns_repository_result(self) -> None:
        service, repo, _ = _make_service()
        session = _make_session()
        repo.seed_session(session)
        caller = _admin_caller(session.tenant_id)
        result = service.get_escalated_for_caller(caller)
        assert result == [session]

    def test_requires_read_application_permission(self) -> None:
        service, _repo, _ = _make_service()
        caller = AuthenticatedUser(user_id=uuid4(), tenant_id=uuid4(), roles=frozenset())
        with pytest.raises(AuthorizationError):
            service.get_escalated_for_caller(caller)
