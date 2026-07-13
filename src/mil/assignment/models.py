"""
ORM models for the Assignment bounded context (spec 005-enterprise-platform
§1, Wave 2 — Relationship Manager / Banker Workspace).

``Assignment`` is the current, mutable "who owns this application" record —
one active row per application (`UNIQUE(application_id)`). Reassignment
never overwrites in place: the previous row is copied into the append-only
``AssignmentHistory`` table first, then the live row is updated — mirroring
the immutable-history discipline already applied to ``RoleAssignment``
(soft-revocation) and ``ReviewAction``.

Schema: ``assignment`` PostgreSQL schema (a dedicated bounded-context schema,
matching the precedent set by ``policy``/``identity``/``evidence``/
``finding`` — not `core`, per the plan's own noted deviation for this reason
in each of those modules).

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mil.kernel.db import Base
from mil.kernel.errors import ValidationError


class Assignment(Base):
    """
    The current ownership record for one application: which Relationship
    Manager originated/owns it, and which Underwriter (if any) is assigned
    to review it.
    """

    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint("application_id", name="uq_assignments_application_id"),
        {"schema": "assignment"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("core.applications.id"), nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("core.users.id"), nullable=False)
    reviewer_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core.users.id"), nullable=True
    )
    assigned_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("core.users.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def create(
        cls,
        *,
        application_id: UUID,
        owner_user_id: UUID,
        assigned_by_user_id: UUID,
        reviewer_user_id: UUID | None = None,
    ) -> Assignment:
        return cls(
            id=uuid4(),
            application_id=application_id,
            owner_user_id=owner_user_id,
            reviewer_user_id=reviewer_user_id,
            assigned_by_user_id=assigned_by_user_id,
            assigned_at=datetime.now(UTC),
        )

    def reassign(
        self,
        *,
        owner_user_id: UUID | None = None,
        reviewer_user_id: UUID | None = None,
        assigned_by_user_id: UUID,
    ) -> None:
        """
        Update ownership/review assignment in place. The caller is
        responsible for archiving the pre-update state into
        ``AssignmentHistory`` first (see ``AssignmentService``) — this
        method only performs the actual mutation.
        """
        if owner_user_id is None and reviewer_user_id is None:
            raise ValidationError("At least one of owner_user_id/reviewer_user_id must be provided")
        if owner_user_id is not None:
            self.owner_user_id = owner_user_id
        if reviewer_user_id is not None:
            self.reviewer_user_id = reviewer_user_id
        self.assigned_by_user_id = assigned_by_user_id
        self.assigned_at = datetime.now(UTC)

    def __repr__(self) -> str:
        return f"<Assignment application={self.application_id} owner={self.owner_user_id}>"


class AssignmentHistory(Base):
    """
    Append-only record of every assignment/reassignment event — a snapshot
    of ``Assignment``'s state at the moment it changed, never updated after
    insertion.
    """

    __tablename__ = "assignment_history"
    __table_args__ = ({"schema": "assignment"},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("core.applications.id"), nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("core.users.id"), nullable=False)
    reviewer_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core.users.id"), nullable=True
    )
    assigned_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("core.users.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    @classmethod
    def snapshot(cls, assignment: Assignment) -> AssignmentHistory:
        return cls(
            id=uuid4(),
            application_id=assignment.application_id,
            owner_user_id=assignment.owner_user_id,
            reviewer_user_id=assignment.reviewer_user_id,
            assigned_by_user_id=assignment.assigned_by_user_id,
            assigned_at=assignment.assigned_at,
            created_at=datetime.now(UTC),
        )

    def __repr__(self) -> str:
        return f"<AssignmentHistory application={self.application_id} owner={self.owner_user_id}>"
