"""
ORM models for the Integration Gateway bounded context (spec 005-enterprise-
platform §2, Wave 2 — LOS Integration Layer).

This module manages *configuration and audit* for LOS integration
(``LOSConnection``, ``LOSSyncEvent``) — the actual read/write mediation is
already implemented by the pre-existing ``mil.kernel.providers.los_adapter
.LOSAdapter`` interface (registered via the DI container, per Constitution
Principle VI). This module does not redefine that interface; it is the
domain layer that lets an ``IntegrationService`` call it and record what
happened, tenant-scoped.

Schema: ``integration`` PostgreSQL schema.

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from mil.kernel.db import Base
from mil.kernel.errors import ValidationError


class LOSConnection(Base):
    """
    Registered LOS integration configuration for a tenant.

    ``vendor_type`` is a free string (matches the existing convention on
    ``Document.document_type``) — the concrete adapter implementation for a
    vendor is a deployment-time DI registration
    (``ProviderRegistry.register_los_adapter``), not something this row
    controls directly; this row is the tenant-visible record that an
    integration exists and its current status.
    """

    __tablename__ = "los_connections"
    __table_args__ = ({"schema": "integration"},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    vendor_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("core.users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    @classmethod
    def create(
        cls, *, tenant_id: UUID, vendor_type: str, created_by_user_id: UUID
    ) -> LOSConnection:
        if not vendor_type or not vendor_type.strip():
            raise ValidationError("vendor_type must not be empty", field="vendor_type")
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            vendor_type=vendor_type.strip(),
            status="ACTIVE",
            created_by_user_id=created_by_user_id,
            created_at=datetime.now(UTC),
        )

    def pause(self) -> None:
        self.status = "PAUSED"

    def resume(self) -> None:
        self.status = "ACTIVE"

    def __repr__(self) -> str:
        return f"<LOSConnection id={self.id} vendor={self.vendor_type} status={self.status}>"


class LOSSyncEvent(Base):
    """
    Immutable, append-only record of one LOS integration call — either an
    inbound read (``read_application``/``read_documents``) or an outbound
    push (``notify_readiness``). Mirrors the immutability discipline already
    applied to ``PolicyResult``/``AuditEvent``.

    Never a duplicate-invention of ``AuditEvent`` (spec's own instruction:
    "integrate naturally with existing audit events rather than introducing
    duplicate event models") — ``IntegrationService`` also emits a real
    ``AuditEvent`` (via the shared ``AuditWriter``) for every sync/push. This
    table exists in addition because it carries LOS-specific detail
    (direction, outcome, the adapter's own error message) that would
    otherwise force ``AuditEvent.event_data``'s untyped JSON to carry
    integration-specific shape nobody else needs to know about — the same
    reasoning that already justifies ``PolicyResult`` existing alongside
    `AuditEvent`` rather than being folded into it.
    """

    __tablename__ = "los_sync_events"
    __table_args__ = ({"schema": "integration"},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("core.applications.id"), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    detail: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    initiated_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("core.users.id"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        application_id: UUID,
        direction: str,
        outcome: str,
        initiated_by_user_id: UUID,
        detail: dict[str, object] | None = None,
        error_message: str | None = None,
    ) -> LOSSyncEvent:
        if direction not in ("INBOUND", "OUTBOUND"):
            raise ValidationError("direction must be INBOUND or OUTBOUND", field="direction")
        if outcome not in ("SUCCESS", "FAILURE"):
            raise ValidationError("outcome must be SUCCESS or FAILURE", field="outcome")
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            application_id=application_id,
            direction=direction,
            outcome=outcome,
            detail=detail or {},
            error_message=error_message,
            initiated_by_user_id=initiated_by_user_id,
            occurred_at=datetime.now(UTC),
        )

    def __repr__(self) -> str:
        return f"<LOSSyncEvent id={self.id} direction={self.direction} outcome={self.outcome}>"
