"""
ReviewService — use-case orchestrator for the Review bounded context
(Engineering Constitution Principle I — Human Decision Authority).

All business rules for human review live here:

- ``start_review`` creates the ``ReviewSession`` (called by the Review
  worker in response to ``PolicyEvaluated``).
- ``assign_reviewer``, ``approve_finding``, ``reject_finding``,
  ``override_finding`` are exclusively human-triggered actions — every one
  requires an authenticated ``actor_user_id``. No AI component may call
  these to reach a verdict.
- ``add_comment`` records free-text discussion.

Every action is recorded as an immutable ``ReviewAction`` (or
``ReviewComment``) row and a synchronous ``AUDIT`` event, in the same
transaction as the caller's other writes (audit is never routed through the
outbox — ADR-007).

"Close review" (a named Sprint 6 responsibility) is not a separate operation:
every terminal action (approve, reject, override) closes the session as part
of its own status transition (``ReviewSession.transition_to`` sets
``closed_at``) — a Finding is reviewed to exactly one final verdict, so there
is no freestanding "close" distinct from reaching that verdict.

``ReviewService`` never evaluates Policy, never generates Findings, never
mutates ``EvidenceItem`` or ``Document`` rows, and never writes to
``finding.findings`` — only ``finding_id`` (a plain reference) is stored.

Dependency rule: imports only from ``mil.review``, ``mil.kernel``, and the
Python standard library. No other bounded context is imported.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mil.kernel.errors import ConflictError, NotFoundError, ValidationError
from mil.kernel.security import Permission, require_permission
from mil.review.models import (
    ACTION_APPROVED,
    ACTION_ASSIGNED,
    ACTION_ESCALATED,
    ACTION_OVERRIDDEN,
    ACTION_REJECTED,
    ACTION_SESSION_STARTED,
    APPROVED,
    OVERRIDDEN,
    REJECTED,
    ReviewAction,
    ReviewComment,
    ReviewSession,
)

if TYPE_CHECKING:
    from uuid import UUID

    from mil.audit.writer import AuditWriter
    from mil.kernel.security import AuthenticatedUser
    from mil.review.repository import ReviewRepository


class ReviewService:
    """
    Orchestrates Review Session creation and human-decision actions.

    Construct per unit of work with a repository and audit writer bound to
    the active session, so that every write and its audit event commit in
    the same transaction as the caller's other writes.
    """

    def __init__(self, repository: ReviewRepository, audit: AuditWriter) -> None:
        self._repo = repository
        self._audit = audit

    # ------------------------------------------------------------------
    # Session creation (system-driven, called by the Review worker)
    # ------------------------------------------------------------------

    def start_review(
        self,
        *,
        finding_id: UUID,
        application_id: UUID,
        tenant_id: UUID,
        workflow_run_id: UUID,
        policy_result_id: UUID,
    ) -> tuple[ReviewSession, bool]:
        """
        Create a new ``ReviewSession`` in ``PENDING_REVIEW`` status for a
        Finding, handing it off for human review.

        Records a ``SESSION_STARTED`` action (system-attributed, no human
        actor yet) and a synchronous ``REVIEW_SESSION_STARTED`` audit event.

        Idempotent replay (ADR-008 §5): if a session already exists for this
        Finding — the race the caller's own up-front ``exists_for_finding``
        check cannot fully close under concurrent workers — that pre-existing
        session is returned instead of raising, paired with ``False``.

        Returns:
            A ``(session, created)`` pair: ``created`` is ``True`` only when
            this call newly persisted the session.
        """
        session = ReviewSession.create(
            finding_id=finding_id,
            application_id=application_id,
            tenant_id=tenant_id,
            workflow_run_id=workflow_run_id,
            policy_result_id=policy_result_id,
        )
        if not self._repo.create_session_if_not_exists(session):
            existing = self._repo.get_session_for_finding(finding_id)
            if existing is None:
                raise ConflictError(
                    f"Review session for finding {finding_id} could not be "
                    "recovered after a uniqueness conflict."
                )
            return existing, False

        action = ReviewAction.create(
            review_session_id=session.id,
            action_type=ACTION_SESSION_STARTED,
            previous_status="",
            new_status=session.status,
        )
        self._repo.save_action(action)

        self._audit.record(
            event_type="REVIEW_SESSION_STARTED",
            entity_type="REVIEW_SESSION",
            entity_id=session.id,
            tenant_id=tenant_id,
            application_id=application_id,
            event_data={"finding_id": str(finding_id), "policy_result_id": str(policy_result_id)},
        )
        return session, True

    # ------------------------------------------------------------------
    # Human-triggered actions (Principle I — every call requires a human actor)
    # ------------------------------------------------------------------

    def assign_reviewer(
        self, session: ReviewSession, *, reviewer_user_id: UUID, assigned_by_user_id: UUID
    ) -> ReviewSession:
        """Assign a reviewer to a session, transitioning it to ``IN_REVIEW``."""
        previous_status = session.status
        session.assign_reviewer(reviewer_user_id)
        self._repo.save_session(session)

        action = ReviewAction.create(
            review_session_id=session.id,
            action_type=ACTION_ASSIGNED,
            actor_user_id=assigned_by_user_id,
            previous_status=previous_status,
            new_status=session.status,
            new_value=str(reviewer_user_id),
        )
        self._repo.save_action(action)

        self._audit.record(
            event_type="REVIEW_REVIEWER_ASSIGNED",
            entity_type="REVIEW_SESSION",
            entity_id=session.id,
            tenant_id=session.tenant_id,
            application_id=session.application_id,
            actor_id=assigned_by_user_id,
            event_data={"reviewer_user_id": str(reviewer_user_id)},
        )
        return session

    def approve_finding(self, session: ReviewSession, *, actor_user_id: UUID) -> ReviewSession:
        """Approve the Finding under review, closing the session as ``APPROVED``."""
        previous_status = session.status
        session.transition_to(APPROVED)
        self._repo.save_session(session)

        action = ReviewAction.create(
            review_session_id=session.id,
            action_type=ACTION_APPROVED,
            actor_user_id=actor_user_id,
            previous_status=previous_status,
            new_status=session.status,
        )
        self._repo.save_action(action)

        self._audit.record(
            event_type="REVIEW_FINDING_APPROVED",
            entity_type="REVIEW_SESSION",
            entity_id=session.id,
            tenant_id=session.tenant_id,
            application_id=session.application_id,
            actor_id=actor_user_id,
            event_data={"finding_id": str(session.finding_id)},
        )
        return session

    def reject_finding(
        self, session: ReviewSession, *, actor_user_id: UUID, reason: str
    ) -> ReviewSession:
        """Reject the Finding under review, closing the session as ``REJECTED``."""
        if not reason or not reason.strip():
            raise ValidationError("reason must not be empty", field="reason")

        previous_status = session.status
        session.transition_to(REJECTED)
        self._repo.save_session(session)

        action = ReviewAction.create(
            review_session_id=session.id,
            action_type=ACTION_REJECTED,
            actor_user_id=actor_user_id,
            previous_status=previous_status,
            new_status=session.status,
            reason=reason,
        )
        self._repo.save_action(action)

        self._audit.record(
            event_type="REVIEW_FINDING_REJECTED",
            entity_type="REVIEW_SESSION",
            entity_id=session.id,
            tenant_id=session.tenant_id,
            application_id=session.application_id,
            actor_id=actor_user_id,
            event_data={"finding_id": str(session.finding_id), "reason": reason},
        )
        return session

    def override_finding(
        self,
        session: ReviewSession,
        *,
        actor_user_id: UUID,
        reason: str,
        previous_value: str,
        new_value: str,
    ) -> ReviewSession:
        """
        Override the Finding under review, closing the session as
        ``OVERRIDDEN``.

        Engineering Constitution Principle I (Human Decision Authority):
        every override MUST capture the reviewer, a timestamp (``created_at``
        on the resulting ``ReviewAction``), a reason, the previous finding
        state, and the new decision. All five are required here and recorded
        permanently — this ``ReviewAction`` row is never updated or deleted.
        """
        if not reason or not reason.strip():
            raise ValidationError("reason must not be empty", field="reason")
        if not new_value or not new_value.strip():
            raise ValidationError("new_value must not be empty", field="new_value")

        previous_status = session.status
        session.transition_to(OVERRIDDEN)
        self._repo.save_session(session)

        action = ReviewAction.create(
            review_session_id=session.id,
            action_type=ACTION_OVERRIDDEN,
            actor_user_id=actor_user_id,
            previous_status=previous_status,
            new_status=session.status,
            reason=reason,
            previous_value=previous_value,
            new_value=new_value,
        )
        self._repo.save_action(action)

        self._audit.record(
            event_type="REVIEW_FINDING_OVERRIDDEN",
            entity_type="REVIEW_SESSION",
            entity_id=session.id,
            tenant_id=session.tenant_id,
            application_id=session.application_id,
            actor_id=actor_user_id,
            event_data={
                "finding_id": str(session.finding_id),
                "reason": reason,
                "previous_value": previous_value,
                "new_value": new_value,
            },
        )
        return session

    def escalate_finding(
        self,
        session: ReviewSession,
        *,
        actor_user_id: UUID,
        reason: str,
        target_role: str,
        target_user_id: UUID | None = None,
    ) -> ReviewSession:
        """
        Escalate the Finding under review to another role's queue.

        ``ESCALATED`` is deliberately not terminal (module docstring):
        ownership transfers away from the escalating reviewer (their
        ``assigned_reviewer_id`` is cleared — see ``ReviewSession.escalate``)
        into the target role's queue, and the same ``approve_finding``,
        ``reject_finding``, and ``override_finding`` methods resolve it —
        there is no separate "resolve escalation" action.
        """
        if not reason or not reason.strip():
            raise ValidationError("reason must not be empty", field="reason")
        if not target_role or not target_role.strip():
            raise ValidationError("target_role must not be empty", field="target_role")

        previous_status = session.status
        session.escalate(target_role=target_role, target_user_id=target_user_id)
        self._repo.save_session(session)

        action = ReviewAction.create(
            review_session_id=session.id,
            action_type=ACTION_ESCALATED,
            actor_user_id=actor_user_id,
            previous_status=previous_status,
            new_status=session.status,
            reason=reason,
            target_role=target_role,
            target_user_id=target_user_id,
        )
        self._repo.save_action(action)

        self._audit.record(
            event_type="REVIEW_FINDING_ESCALATED",
            entity_type="REVIEW_SESSION",
            entity_id=session.id,
            tenant_id=session.tenant_id,
            application_id=session.application_id,
            actor_id=actor_user_id,
            event_data={
                "finding_id": str(session.finding_id),
                "reason": reason,
                "target_role": target_role,
                "target_user_id": str(target_user_id) if target_user_id is not None else None,
            },
        )
        return session

    def add_comment(
        self, session: ReviewSession, *, author_user_id: UUID, comment_text: str
    ) -> ReviewComment:
        """Add a free-text comment to a Review Session."""
        comment = ReviewComment.create(
            review_session_id=session.id,
            author_user_id=author_user_id,
            comment_text=comment_text,
        )
        self._repo.save_comment(comment)

        self._audit.record(
            event_type="REVIEW_COMMENT_ADDED",
            entity_type="REVIEW_SESSION",
            entity_id=session.id,
            tenant_id=session.tenant_id,
            application_id=session.application_id,
            actor_id=author_user_id,
            event_data={"comment_id": str(comment.id)},
        )
        return comment

    # ------------------------------------------------------------------
    # Collaboration (spec 005-enterprise-platform §9) — new methods, added
    # purely additively. Unlike `add_comment` above (unchanged, pre-existing,
    # no `caller`/permission self-check, to stay compatible with its
    # existing callers/tests), these new methods DO take `caller` and
    # self-check, matching the convention established by `IdentityService`/
    # `PolicyService`'s new maker-checker methods in this same wave.
    # ------------------------------------------------------------------

    def get_session_for_finding(
        self, caller: AuthenticatedUser, finding_id: UUID
    ) -> ReviewSession:
        require_permission(caller, Permission.COMMENT_ON_FINDING)
        session = self._repo.get_session_for_finding(finding_id)
        if session is None or session.tenant_id != caller.tenant_id:
            raise NotFoundError("ReviewSession", f"finding={finding_id}")
        return session

    def get_comments_for_finding(
        self, caller: AuthenticatedUser, finding_id: UUID
    ) -> list[ReviewComment]:
        session = self.get_session_for_finding(caller, finding_id)
        return self._repo.get_comments_for_session(session.id)

    def post_comment(
        self,
        caller: AuthenticatedUser,
        finding_id: UUID,
        *,
        comment_text: str,
        mentioned_user_ids: list[UUID] | None = None,
    ) -> tuple[ReviewComment, UUID]:
        """
        Post a comment on a Finding's Review Session.

        Returns:
            A ``(comment, audit_event_id)`` pair — the audit event id lets
            the caller (the API route) create a Notification pointing at
            this exact event for each mentioned user (spec 005 §13, Wave 2)
            without this service importing ``mil.notification`` itself
            (dependency rule).

        Raises:
            NotFoundError: If no Review Session exists yet for this Finding
                (a comment can only be posted once the Finding is under
                review — matching the real lifecycle, not an application-
                wide free-for-all thread).
        """
        require_permission(caller, Permission.COMMENT_ON_FINDING)
        session = self.get_session_for_finding(caller, finding_id)
        comment = ReviewComment.create(
            review_session_id=session.id,
            author_user_id=caller.user_id,
            comment_text=comment_text,
            mentioned_user_ids=mentioned_user_ids or [],
        )
        self._repo.save_comment(comment)
        event = self._audit.record(
            event_type="REVIEW_COMMENT_ADDED",
            entity_type="REVIEW_SESSION",
            entity_id=session.id,
            tenant_id=session.tenant_id,
            application_id=session.application_id,
            actor_id=caller.user_id,
            event_data={
                "comment_id": str(comment.id),
                "mentioned_user_ids": [str(uid) for uid in (mentioned_user_ids or [])],
            },
        )
        return comment, event.id

    def get_comment(self, caller: AuthenticatedUser, comment_id: UUID) -> ReviewComment:
        require_permission(caller, Permission.COMMENT_ON_FINDING)
        comment = self._repo.get_comment_by_id(comment_id)
        if comment is None:
            raise NotFoundError("ReviewComment", comment_id)
        session = self._repo.get_session_by_id(comment.review_session_id)
        if session is None or session.tenant_id != caller.tenant_id:
            raise NotFoundError("ReviewComment", comment_id)
        return comment

    def edit_comment(
        self, caller: AuthenticatedUser, comment: ReviewComment, new_text: str
    ) -> ReviewComment:
        """
        Edit a comment. Raises ``AuthorizationError`` (from ``ReviewComment
        .edit``) if the caller isn't the author, or ``ConflictError`` if the
        edit window has elapsed.
        """
        require_permission(caller, Permission.COMMENT_ON_FINDING)
        comment.edit(caller.user_id, new_text)
        self._repo.save_comment(comment)
        return comment

    def delete_comment(self, caller: AuthenticatedUser, comment: ReviewComment) -> ReviewComment:
        require_permission(caller, Permission.COMMENT_ON_FINDING)
        comment.soft_delete(caller.user_id)
        self._repo.save_comment(comment)
        return comment
