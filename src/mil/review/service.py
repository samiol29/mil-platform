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

from mil.kernel.errors import ValidationError
from mil.review.models import (
    ACTION_APPROVED,
    ACTION_ASSIGNED,
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
    ) -> ReviewSession:
        """
        Create a new ``ReviewSession`` in ``PENDING_REVIEW`` status for a
        Finding, handing it off for human review.

        Records a ``SESSION_STARTED`` action (system-attributed, no human
        actor yet) and a synchronous ``REVIEW_SESSION_STARTED`` audit event.
        """
        session = ReviewSession.create(
            finding_id=finding_id,
            application_id=application_id,
            tenant_id=tenant_id,
            workflow_run_id=workflow_run_id,
            policy_result_id=policy_result_id,
        )
        self._repo.save_session(session)

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
        return session

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
