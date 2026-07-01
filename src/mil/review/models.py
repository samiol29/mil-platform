"""
ORM models for the Review bounded context (Engineering Constitution
Principle I — Human Decision Authority).

Three entities, deliberately normalized:

- ``ReviewSession`` — the mutable "current state" of one Finding's human
  review: status, assigned reviewer, timestamps. One session per Finding
  (unique on ``finding_id``) — a Finding is produced once (Sprint 4) and is
  never re-evaluated, so it is reviewed at most once.
- ``ReviewAction`` — the append-only, immutable log of every status
  transition applied to a session (assign, approve, reject, override).
  Override records are ``ReviewAction`` rows with ``action_type ==
  "OVERRIDDEN"`` rather than a separate table: every action already carries
  full attribution (actor, timestamp, reason, previous/new status,
  previous/new value), which is exactly what an override record requires —
  a fourth table would duplicate these columns for no additional
  information. This is the normalized-schema justification referenced by
  migration 0008.
- ``ReviewComment`` — append-only free-text discussion, distinct from the
  formal action log.

No row in this module ever references ``mil.finding.models.Finding`` for
mutation — Review never writes to ``finding.findings`` (Finding rows are
immutable once created, Sprint 4). Only ``finding_id`` (a plain FK) is stored.

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from mil.kernel.db import Base
from mil.kernel.errors import InvalidStateTransitionError, ValidationError

# ---------------------------------------------------------------------------
# ReviewStatus (enumeration)
# ---------------------------------------------------------------------------

PENDING_REVIEW = "PENDING_REVIEW"
IN_REVIEW = "IN_REVIEW"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
OVERRIDDEN = "OVERRIDDEN"

TERMINAL_STATUSES: frozenset[str] = frozenset({APPROVED, REJECTED, OVERRIDDEN})

# Valid status transitions: {from_status: {allowed to_status, ...}}
_VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    PENDING_REVIEW: frozenset({IN_REVIEW}),
    IN_REVIEW: frozenset({APPROVED, REJECTED, OVERRIDDEN}),
    APPROVED: frozenset(),
    REJECTED: frozenset(),
    OVERRIDDEN: frozenset(),
}

# ---------------------------------------------------------------------------
# ReviewAction action_type constants
# ---------------------------------------------------------------------------

ACTION_SESSION_STARTED = "SESSION_STARTED"
ACTION_ASSIGNED = "ASSIGNED"
ACTION_APPROVED = "APPROVED"
ACTION_REJECTED = "REJECTED"
ACTION_OVERRIDDEN = "OVERRIDDEN"


class ReviewSession(Base):
    """
    The current state of one Finding's human review.

    Created once, in ``PENDING_REVIEW`` status, when the Review worker
    consumes ``PolicyEvaluated`` for a Finding. All subsequent state changes
    are driven exclusively by a human actor via ``ReviewService`` — no AI
    component may transition a session (Principle I).
    """

    __tablename__ = "review_sessions"
    __table_args__ = ({"schema": "review"},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    finding_id: Mapped[UUID] = mapped_column(
        ForeignKey("finding.findings.id"), nullable=False, unique=True
    )
    application_id: Mapped[UUID] = mapped_column(ForeignKey("core.applications.id"), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    workflow_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("orchestrator.workflow_runs.id"), nullable=False
    )
    policy_result_id: Mapped[UUID] = mapped_column(
        ForeignKey("policy.policy_results.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=PENDING_REVIEW)
    assigned_reviewer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core.users.id"), nullable=True
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        finding_id: UUID,
        application_id: UUID,
        tenant_id: UUID,
        workflow_run_id: UUID,
        policy_result_id: UUID,
    ) -> ReviewSession:
        """Create a new Review Session in ``PENDING_REVIEW`` status."""
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            finding_id=finding_id,
            application_id=application_id,
            tenant_id=tenant_id,
            workflow_run_id=workflow_run_id,
            policy_result_id=policy_result_id,
            status=PENDING_REVIEW,
            created_at=now,
            updated_at=now,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def transition_to(self, new_status: str) -> None:
        """
        Transition this session to ``new_status``.

        Raises:
            InvalidStateTransitionError: If the transition is not permitted
                by the review status graph.
        """
        allowed = _VALID_TRANSITIONS.get(self.status, frozenset())
        if new_status not in allowed:
            raise InvalidStateTransitionError(
                entity_type="ReviewSession",
                entity_id=self.id,
                from_state=self.status,
                to_state=new_status,
            )
        self.status = new_status
        self.updated_at = datetime.now(UTC)
        if new_status in TERMINAL_STATUSES:
            self.closed_at = self.updated_at

    def assign_reviewer(self, reviewer_id: UUID) -> None:
        """Assign a reviewer and transition PENDING_REVIEW -> IN_REVIEW."""
        self.transition_to(IN_REVIEW)
        self.assigned_reviewer_id = reviewer_id
        self.assigned_at = self.updated_at

    @property
    def is_terminal(self) -> bool:
        """Return ``True`` if this session has reached a final decision."""
        return self.status in TERMINAL_STATUSES

    @property
    def status_enum(self) -> str:
        """Return the current status (kept for symmetry with other aggregates)."""
        return self.status

    def __repr__(self) -> str:
        return f"<ReviewSession id={self.id} finding={self.finding_id} status={self.status}>"


class ReviewAction(Base):
    """
    Immutable, append-only record of one status transition applied to a
    ``ReviewSession``.

    Every action carries full attribution: actor, timestamp, the status
    before and after, and (for reject/override) a reason and the previous
    and new values. An override record is simply a ``ReviewAction`` row with
    ``action_type == "OVERRIDDEN"`` — see module docstring.

    ``actor_user_id`` is nullable: the session-creation action
    (``SESSION_STARTED``) is system-driven (the Review worker), not a human
    action; every subsequent action (assign, approve, reject, override) is
    always attributed to an authenticated human user (Principle I).
    """

    __tablename__ = "review_actions"
    __table_args__ = ({"schema": "review"},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    review_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("review.review_sessions.id"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("core.users.id"), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    previous_status: Mapped[str] = mapped_column(String(50), nullable=False)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def create(
        cls,
        *,
        review_session_id: UUID,
        action_type: str,
        previous_status: str,
        new_status: str,
        actor_user_id: UUID | None = None,
        reason: str | None = None,
        previous_value: str | None = None,
        new_value: str | None = None,
    ) -> ReviewAction:
        """
        Build an immutable review action.

        Raises:
            ValidationError: If ``actor_user_id`` is ``None`` for a
                human-attributable action type (anything other than
                ``SESSION_STARTED``), or if ``action_type`` is empty.
        """
        if not action_type:
            raise ValidationError("action_type must not be empty", field="action_type")
        if action_type != ACTION_SESSION_STARTED and actor_user_id is None:
            raise ValidationError(
                f"action_type {action_type!r} requires a human actor (Principle I)",
                field="actor_user_id",
            )

        return cls(
            id=uuid4(),
            review_session_id=review_session_id,
            action_type=action_type,
            actor_user_id=actor_user_id,
            actor_type="SYSTEM" if actor_user_id is None else "USER",
            previous_status=previous_status,
            new_status=new_status,
            reason=reason,
            previous_value=previous_value,
            new_value=new_value,
            created_at=datetime.now(UTC),
        )

    @property
    def is_override(self) -> bool:
        """Return ``True`` if this action recorded a human override."""
        return self.action_type == ACTION_OVERRIDDEN

    def __repr__(self) -> str:
        return (
            f"<ReviewAction id={self.id} session={self.review_session_id} "
            f"type={self.action_type} {self.previous_status}->{self.new_status}>"
        )


class ReviewComment(Base):
    """
    Immutable, append-only free-text comment on a ``ReviewSession``.

    Distinct from ``ReviewAction``: comments are discussion, not formal
    status-changing decisions, and always carry a human author.
    """

    __tablename__ = "review_comments"
    __table_args__ = ({"schema": "review"},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    review_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("review.review_sessions.id"), nullable=False
    )
    author_user_id: Mapped[UUID] = mapped_column(ForeignKey("core.users.id"), nullable=False)
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def create(
        cls, *, review_session_id: UUID, author_user_id: UUID, comment_text: str
    ) -> ReviewComment:
        if not comment_text or not comment_text.strip():
            raise ValidationError("comment_text must not be empty", field="comment_text")

        return cls(
            id=uuid4(),
            review_session_id=review_session_id,
            author_user_id=author_user_id,
            comment_text=comment_text,
            created_at=datetime.now(UTC),
        )

    def __repr__(self) -> str:
        return f"<ReviewComment id={self.id} session={self.review_session_id}>"
