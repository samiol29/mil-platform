"""
Persistence gateway for the Review bounded context.

``ReviewRepository`` covers all three Review entities:

- ``ReviewSession`` — mutable current-state row; ``save_session`` handles
  both create and update (create sets it once, subsequent status
  transitions flush the same row).
- ``ReviewAction`` / ``ReviewComment`` — append-only: writes immutable rows
  and never updates or deletes them.

None of these methods commit — the caller (the Review worker's per-job Unit
of Work, or the future review-action composition root) owns the transaction.

Idempotency (ADR-008): ``exists_for_finding`` lets the Review worker detect a
replay (a session already exists for this Finding) and treat it as a no-op
rather than creating a duplicate; the unique constraint on
``review_sessions.finding_id`` is the backing authority.

Dependency rule: imports only from ``mil.review.models``, ``mil.kernel``, and
the Python standard library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from mil.review.models import (
    ESCALATED,
    TERMINAL_STATUSES,
    ReviewAction,
    ReviewComment,
    ReviewSession,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session


class ReviewRepository:
    """Persistence gateway for ``ReviewSession``, ``ReviewAction``, and ``ReviewComment`` rows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # ReviewSession
    # ------------------------------------------------------------------

    def save_session(self, review_session: ReviewSession) -> None:
        """Persist a Review Session (create or update). Adds and flushes."""
        self._session.add(review_session)
        self._session.flush()

    def create_session_if_not_exists(self, review_session: ReviewSession) -> bool:
        """
        Persist a brand-new Review Session, treating a uniqueness violation
        (a session already exists for this Finding) as proof one was already
        committed by a prior attempt (ADR-008 §5) rather than an error — the
        authoritative fallback beneath ``exists_for_finding``'s read-then-write
        check, which alone is subject to a race between concurrent workers.
        Isolated with a SAVEPOINT (``session.begin_nested``) so a collision
        here cannot poison the caller's per-job Unit of Work.

        Only for the *create* path (``ReviewService.start_review``) — every
        subsequent status transition on an existing session goes through
        ``save_session`` as an ordinary update, which cannot violate this
        constraint (``finding_id`` never changes after creation).

        Returns:
            ``True`` if this call newly persisted the session, ``False`` if
            one already existed (a replay no-op).
        """
        try:
            with self._session.begin_nested():
                self._session.add(review_session)
                self._session.flush()
        except IntegrityError:
            return False
        return True

    def get_session_by_id(self, review_session_id: UUID) -> ReviewSession | None:
        """Return the Review Session with the given id, or ``None``."""
        return self._session.get(ReviewSession, review_session_id)

    def get_session_for_finding(self, finding_id: UUID) -> ReviewSession | None:
        """Return the Review Session for a Finding, or ``None`` if none exists."""
        stmt = select(ReviewSession).where(ReviewSession.finding_id == finding_id)
        return self._session.scalars(stmt).one_or_none()

    def exists_for_finding(self, finding_id: UUID) -> bool:
        """
        Return ``True`` if a Review Session already exists for a Finding.

        This is the job-level idempotency check (ADR-008): a non-``False``
        result means this Finding has already been handed off for review,
        within the same all-or-nothing per-job transaction.
        """
        stmt = select(ReviewSession.id).where(ReviewSession.finding_id == finding_id)
        return self._session.scalars(stmt).first() is not None

    def get_pending_reviews_for_tenant(self, tenant_id: UUID) -> list[ReviewSession]:
        """Return every non-terminal Review Session for a tenant, oldest first."""
        stmt = (
            select(ReviewSession)
            .where(
                ReviewSession.tenant_id == tenant_id,
                ReviewSession.status.not_in(TERMINAL_STATUSES),
            )
            .order_by(ReviewSession.created_at.asc())
        )
        return list(self._session.scalars(stmt))

    def get_escalated_for_role(self, tenant_id: UUID, role: str) -> list[ReviewSession]:
        """
        Return every Review Session currently escalated to ``role``, oldest
        first — the target role's escalation queue.

        Not yet wired to an HTTP endpoint (queue endpoints are User Story 2);
        provided now so the data-level "escalation places it into the target
        role's queue" effect is actually queryable once that endpoint exists.
        """
        stmt = (
            select(ReviewSession)
            .where(
                ReviewSession.tenant_id == tenant_id,
                ReviewSession.status == ESCALATED,
                ReviewSession.escalated_to_role == role,
            )
            .order_by(ReviewSession.updated_at.asc())
        )
        return list(self._session.scalars(stmt))

    # ------------------------------------------------------------------
    # ReviewAction (append-only)
    # ------------------------------------------------------------------

    def save_action(self, action: ReviewAction) -> None:
        """Persist an immutable review action. Adds and flushes."""
        self._session.add(action)
        self._session.flush()

    def get_actions_for_session(self, review_session_id: UUID) -> list[ReviewAction]:
        """Return the full, ordered action history for a Review Session."""
        stmt = (
            select(ReviewAction)
            .where(ReviewAction.review_session_id == review_session_id)
            .order_by(ReviewAction.created_at.asc())
        )
        return list(self._session.scalars(stmt))

    # ------------------------------------------------------------------
    # ReviewComment (append-only)
    # ------------------------------------------------------------------

    def save_comment(self, comment: ReviewComment) -> None:
        """Persist an immutable review comment. Adds and flushes."""
        self._session.add(comment)
        self._session.flush()

    def get_comments_for_session(self, review_session_id: UUID) -> list[ReviewComment]:
        """Return every comment on a Review Session, oldest first."""
        stmt = (
            select(ReviewComment)
            .where(ReviewComment.review_session_id == review_session_id)
            .order_by(ReviewComment.created_at.asc())
        )
        return list(self._session.scalars(stmt))
