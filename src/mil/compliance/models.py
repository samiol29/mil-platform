"""
ORM models for the Security & Compliance bounded context (spec 005-
enterprise-platform §16, Wave 4).

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from mil.kernel.db import Base
from mil.kernel.errors import ValidationError

ARCHIVE = "ARCHIVE"
DELETE = "DELETE"

# Categories for which DELETE is never a valid retention action (Principle
# VIII — audit/evidence immutability). Enforced here AND by a database
# CHECK constraint in the migration — defense in depth, not either/or.
_NEVER_DELETABLE_CATEGORIES = frozenset({"AUDIT_EVENT", "EVIDENCE"})


class DataRetentionPolicy(Base):
    """A configurable, per-tenant, per-data-category retention policy."""

    __tablename__ = "data_retention_policies"
    __table_args__ = (
        CheckConstraint(
            "NOT (data_category IN ('AUDIT_EVENT', 'EVIDENCE') AND action = 'DELETE')",
            name="ck_data_retention_policies_no_delete_audit_evidence",
        ),
        {"schema": "compliance"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    data_category: Mapped[str] = mapped_column(String(50), nullable=False)
    retention_period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        data_category: str,
        retention_period_days: int,
        action: str,
    ) -> DataRetentionPolicy:
        if action not in (ARCHIVE, DELETE):
            raise ValidationError("action must be ARCHIVE or DELETE", field="action")
        if action == DELETE and data_category in _NEVER_DELETABLE_CATEGORIES:
            raise ValidationError(
                f"DELETE is not permitted for {data_category} — audit/evidence records are "
                "immutable per Constitution Principle VIII",
                field="action",
            )
        if retention_period_days <= 0:
            raise ValidationError(
                "retention_period_days must be positive", field="retention_period_days"
            )
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            data_category=data_category,
            retention_period_days=retention_period_days,
            action=action,
        )

    def __repr__(self) -> str:
        return (
            f"<DataRetentionPolicy id={self.id} category={self.data_category} "
            f"action={self.action} days={self.retention_period_days}>"
        )


class ConsentRecord(Base):
    """
    An explicit, timestamped, versioned consent record. Exactly one of
    ``party_id``/``portal_account_id`` is set (enforced by a database CHECK
    constraint in the migration, mirroring this model's own validation).
    """

    __tablename__ = "consent_records"
    __table_args__ = (
        CheckConstraint(
            "(party_id IS NOT NULL AND portal_account_id IS NULL) OR "
            "(party_id IS NULL AND portal_account_id IS NOT NULL)",
            name="ck_consent_records_exactly_one_subject",
        ),
        {"schema": "compliance"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    party_id: Mapped[UUID | None] = mapped_column(ForeignKey("core.parties.id"), nullable=True)
    portal_account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("portal.portal_accounts.id"), nullable=True
    )
    consent_type: Mapped[str] = mapped_column(String(100), nullable=False)
    consent_text_version: Mapped[str] = mapped_column(String(50), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @classmethod
    def grant(
        cls,
        *,
        consent_type: str,
        consent_text_version: str,
        party_id: UUID | None = None,
        portal_account_id: UUID | None = None,
    ) -> ConsentRecord:
        if (party_id is None) == (portal_account_id is None):
            raise ValidationError(
                "Exactly one of party_id/portal_account_id must be set", field="party_id"
            )
        if not consent_type or not consent_type.strip():
            raise ValidationError("consent_type must not be empty", field="consent_type")
        return cls(
            id=uuid4(),
            party_id=party_id,
            portal_account_id=portal_account_id,
            consent_type=consent_type.strip(),
            consent_text_version=consent_text_version,
            granted_at=datetime.now(UTC),
        )

    def withdraw(self) -> None:
        """Record consent withdrawal. Idempotent."""
        if self.withdrawn_at is None:
            self.withdrawn_at = datetime.now(UTC)

    def __repr__(self) -> str:
        return f"<ConsentRecord id={self.id} type={self.consent_type}>"
