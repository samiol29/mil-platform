"""
ORM models for the Borrower Identity Resolution bounded context (spec 005-
enterprise-platform §5, Wave 3).

Three entities:

- ``IdentityMatchCandidate`` — an advisory, human-reviewable suggestion that
  two ``Party`` rows (from different applications) represent the same
  borrower. Never auto-applied.
- ``BorrowerIdentity`` — the confirmed, resolved identity record. Created
  the first time a candidate is confirmed.
- ``BorrowerIdentityMember`` — one ``Party``/application linked into a
  ``BorrowerIdentity``. Append-only membership — a party is never silently
  unlinked; identity corrections are new events (spec's own "support
  identity corrections" requirement), see ``BorrowerIdentityMember.unlinked_at``.

Schema: ``borrower_identity`` PostgreSQL schema.

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from mil.kernel.db import Base
from mil.kernel.errors import ConflictError, ValidationError


class IdentityMatchCandidate(Base):
    """
    An advisory identity-match suggestion between two parties.

    ``match_basis`` is a JSON explanation of exactly which signals
    contributed (e.g. ``{"exact_identifier_match": true}`` or
    ``{"name_similarity": "exact_normalized_match"}``) — Principle III
    (Explainability) applied to identity matching: a reviewer must be able
    to see *why* a match was suggested, never a bare opaque score.
    """

    __tablename__ = "identity_match_candidates"
    __table_args__ = ({"schema": "borrower_identity"},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    party_id: Mapped[UUID] = mapped_column(ForeignKey("core.parties.id"), nullable=False)
    candidate_party_id: Mapped[UUID] = mapped_column(ForeignKey("core.parties.id"), nullable=False)
    match_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    match_basis: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core.users.id"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        party_id: UUID,
        candidate_party_id: UUID,
        match_score: float,
        match_basis: dict[str, object],
    ) -> IdentityMatchCandidate:
        if party_id == candidate_party_id:
            raise ValidationError("A party cannot be matched against itself", field="candidate_party_id")
        if not (0.0 <= match_score <= 1.0):
            raise ValidationError("match_score must be between 0.0 and 1.0", field="match_score")
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            party_id=party_id,
            candidate_party_id=candidate_party_id,
            match_score=match_score,
            match_basis=match_basis,
            status="PENDING",
            created_at=datetime.now(UTC),
        )

    def confirm(self, reviewed_by_user_id: UUID) -> None:
        if self.status != "PENDING":
            raise ConflictError(f"IdentityMatchCandidate {self.id} has already been reviewed")
        self.status = "CONFIRMED"
        self.reviewed_by_user_id = reviewed_by_user_id
        self.reviewed_at = datetime.now(UTC)

    def reject(self, reviewed_by_user_id: UUID, reason: str | None = None) -> None:
        if self.status != "PENDING":
            raise ConflictError(f"IdentityMatchCandidate {self.id} has already been reviewed")
        self.status = "REJECTED"
        self.reviewed_by_user_id = reviewed_by_user_id
        self.reason = reason
        self.reviewed_at = datetime.now(UTC)

    def __repr__(self) -> str:
        return f"<IdentityMatchCandidate id={self.id} status={self.status} score={self.match_score}>"


class BorrowerIdentity(Base):
    """
    A confirmed, resolved borrower identity — created the first time a
    candidate involving a party is confirmed. All member parties/
    applications are then reachable through ``BorrowerIdentityMember``.
    """

    __tablename__ = "borrower_identities"
    __table_args__ = ({"schema": "borrower_identity"},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    # A real, already-fetched display name (from the first-linked Party) —
    # never a fabricated "full legal name"; MIL doesn't have one.
    primary_display_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    @classmethod
    def create(cls, *, tenant_id: UUID, primary_display_name: str) -> BorrowerIdentity:
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            primary_display_name=primary_display_name,
            created_at=datetime.now(UTC),
        )

    def __repr__(self) -> str:
        return f"<BorrowerIdentity id={self.id} name={self.primary_display_name!r}>"


class BorrowerIdentityMember(Base):
    """
    One ``Party`` (and its owning application) linked into a
    ``BorrowerIdentity``. Append-only: a correction unlinks by setting
    ``unlinked_at`` (spec's "support identity corrections" requirement),
    never by deleting the row — preserves the historical fact that this
    link existed and who created/removed it.
    """

    __tablename__ = "borrower_identity_members"
    __table_args__ = ({"schema": "borrower_identity"},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    borrower_identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("borrower_identity.borrower_identities.id"), nullable=False
    )
    party_id: Mapped[UUID] = mapped_column(ForeignKey("core.parties.id"), nullable=False)
    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.applications.id"), nullable=False
    )
    linked_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("core.users.id"), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    unlinked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unlinked_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core.users.id"), nullable=True
    )

    @classmethod
    def create(
        cls,
        *,
        borrower_identity_id: UUID,
        party_id: UUID,
        application_id: UUID,
        linked_by_user_id: UUID,
    ) -> BorrowerIdentityMember:
        return cls(
            id=uuid4(),
            borrower_identity_id=borrower_identity_id,
            party_id=party_id,
            application_id=application_id,
            linked_by_user_id=linked_by_user_id,
            linked_at=datetime.now(UTC),
        )

    def unlink(self, unlinked_by_user_id: UUID) -> None:
        if self.unlinked_at is not None:
            raise ConflictError(f"BorrowerIdentityMember {self.id} is already unlinked")
        self.unlinked_at = datetime.now(UTC)
        self.unlinked_by_user_id = unlinked_by_user_id

    @property
    def is_active(self) -> bool:
        return self.unlinked_at is None

    def __repr__(self) -> str:
        return f"<BorrowerIdentityMember identity={self.borrower_identity_id} party={self.party_id}>"
