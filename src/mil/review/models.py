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

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from mil.kernel.db import Base
from mil.kernel.errors import (
    AuthorizationError,
    ConflictError,
    InvalidStateTransitionError,
    ValidationError,
)

# ---------------------------------------------------------------------------
# ReviewStatus (enumeration)
# ---------------------------------------------------------------------------

PENDING_REVIEW = "PENDING_REVIEW"
IN_REVIEW = "IN_REVIEW"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
OVERRIDDEN = "OVERRIDDEN"
ESCALATED = "ESCALATED"

# ESCALATED is deliberately NOT terminal (see module docstring / docs/archive/HANDOFF.md's
# domain-design review): an escalated Finding is still awaiting a decision —
# it has simply moved to a different role's queue — and is resolved by the
# same approve/reject/override actions any other in-review Finding is.
TERMINAL_STATUSES: frozenset[str] = frozenset({APPROVED, REJECTED, OVERRIDDEN})

# Valid status transitions: {from_status: {allowed to_status, ...}}
_VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    PENDING_REVIEW: frozenset({IN_REVIEW, ESCALATED}),
    IN_REVIEW: frozenset({APPROVED, REJECTED, OVERRIDDEN, ESCALATED}),
    # An escalated session resolves via the ordinary decision actions, or may
    # be re-escalated (e.g. Compliance escalates further to Risk).
    ESCALATED: frozenset({APPROVED, REJECTED, OVERRIDDEN, ESCALATED}),
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
ACTION_ESCALATED = "ESCALATED"


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
    # Current-state escalation target (mutable — reflects the *latest*
    # escalation, if any; historical targets live on the ReviewAction log).
    escalated_to_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    escalated_to_user_id: Mapped[UUID | None] = mapped_column(
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

    def escalate(self, *, target_role: str, target_user_id: UUID | None = None) -> None:
        """
        Transition to ESCALATED, transferring ownership to another role's
        queue (and, optionally, a specific person within it).

        This clears ``assigned_reviewer_id``: the escalating reviewer no
        longer owns this Finding, per the approved design ("escalation
        removes the finding from the current reviewer's queue").
        """
        self.transition_to(ESCALATED)
        self.escalated_to_role = target_role
        self.escalated_to_user_id = target_user_id
        self.assigned_reviewer_id = None

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
    # Populated only for ACTION_ESCALATED — an immutable snapshot of who this
    # specific escalation targeted (the session's own escalated_to_* columns
    # hold only the *latest* target; this is the historical record).
    target_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("core.users.id"), nullable=True)
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
        target_role: str | None = None,
        target_user_id: UUID | None = None,
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
            target_role=target_role,
            target_user_id=target_user_id,
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


#: FR-COLLAB-004 (spec 005-enterprise-platform §9): a comment may be edited
#: by its author within this window; afterward it is immutable (matches the
#: append-only discipline this class already documents) except for the
#: honest "edited" marker itself.
COMMENT_EDIT_WINDOW = timedelta(minutes=5)


class ReviewComment(Base):
    """
    Free-text discussion on a ``ReviewSession`` — i.e. on one Finding's
    review (Collaboration, spec 005-enterprise-platform §9).

    Distinct from ``ReviewAction``: comments are discussion, not formal
    status-changing decisions, and always carry a human author.

    Originally append-only/immutable; spec 005 §9 adds a narrow, honest
    exception: the author may edit within ``COMMENT_EDIT_WINDOW`` (setting
    ``edited_at``, never silently rewriting history) and may soft-delete at
    any time (``deleted_at``) — never a hard delete, preserving the
    immutable-audit-trail spirit of the rest of this module.

    ``mentioned_user_ids`` is a plain list of user ids the comment
    @-mentions — resolved and validated by the caller (the API layer,
    composed with ``mil.identity``) before this row is created; this module
    itself has no dependency on Identity (dependency rule).
    """

    __tablename__ = "review_comments"
    __table_args__ = ({"schema": "review"},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    review_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("review.review_sessions.id"), nullable=False
    )
    author_user_id: Mapped[UUID] = mapped_column(ForeignKey("core.users.id"), nullable=False)
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    mentioned_user_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def create(
        cls,
        *,
        review_session_id: UUID,
        author_user_id: UUID,
        comment_text: str,
        mentioned_user_ids: list[UUID] | None = None,
    ) -> ReviewComment:
        if not comment_text or not comment_text.strip():
            raise ValidationError("comment_text must not be empty", field="comment_text")

        return cls(
            id=uuid4(),
            review_session_id=review_session_id,
            author_user_id=author_user_id,
            comment_text=comment_text,
            mentioned_user_ids=[str(uid) for uid in (mentioned_user_ids or [])],
            created_at=datetime.now(UTC),
        )

    def edit(self, author_user_id: UUID, new_text: str) -> None:
        """
        Edit this comment's text.

        Raises:
            AuthorizationError: If ``author_user_id`` is not this comment's
                author.
            ConflictError: If the edit window has elapsed, or the comment is
                deleted.
            ValidationError: If ``new_text`` is empty.
        """
        if self.deleted_at is not None:
            raise ConflictError(f"ReviewComment {self.id} has been deleted")
        if author_user_id != self.author_user_id:
            raise AuthorizationError("Only a comment's author may edit it.")
        if datetime.now(UTC) - self.created_at > COMMENT_EDIT_WINDOW:
            raise ConflictError(
                f"ReviewComment {self.id}'s edit window ({COMMENT_EDIT_WINDOW}) has elapsed"
            )
        if not new_text or not new_text.strip():
            raise ValidationError("comment_text must not be empty", field="comment_text")
        self.comment_text = new_text
        self.edited_at = datetime.now(UTC)

    def soft_delete(self, author_user_id: UUID) -> None:
        """
        Soft-delete this comment (never a hard delete — Principle VIII's
        immutable-history spirit).

        Raises:
            AuthorizationError: If ``author_user_id`` is not this comment's
                author.
        """
        if author_user_id != self.author_user_id:
            raise AuthorizationError("Only a comment's author may delete it.")
        if self.deleted_at is None:
            self.deleted_at = datetime.now(UTC)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def __repr__(self) -> str:
        return f"<ReviewComment id={self.id} session={self.review_session_id}>"
