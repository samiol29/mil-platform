"""
ORM model for the Notification bounded context (spec 005-enterprise-
platform §13, Wave 2).

``Notification`` deliberately carries no ``notification_type``/``title``/
``body`` of its own — it is a pointer (``audit_event_id``) to the real,
already-written ``AuditEvent`` that triggered it, plus per-recipient read
state. This is the literal interpretation of the spec's own instruction:
"integrate naturally with existing audit events rather than introducing
duplicate event models." Rendering a human-readable notification message is
the API/frontend's job (reading the referenced event's ``event_type``/
``event_data``), exactly as the Timeline region already does for the
narrative view of the same audit data.

Schema: ``notification`` PostgreSQL schema.

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from mil.kernel.db import Base


class Notification(Base):
    """
    A per-recipient pointer to an ``AuditEvent``, with read state.

    ``recipient_user_id`` is who should see it; ``audit_event_id`` is the
    real event that triggered it. Never duplicated event data — a
    notification with no resolvable audit event behind it should never
    exist (enforced by the FK, not just convention).
    """

    __tablename__ = "notifications"
    __table_args__ = ({"schema": "notification"},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    recipient_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.users.id"), nullable=False
    )
    audit_event_id: Mapped[UUID] = mapped_column(
        ForeignKey("audit.audit_events.id"), nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    @classmethod
    def create(
        cls, *, tenant_id: UUID, recipient_user_id: UUID, audit_event_id: UUID
    ) -> Notification:
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            recipient_user_id=recipient_user_id,
            audit_event_id=audit_event_id,
            read_at=None,
            created_at=datetime.now(UTC),
        )

    def mark_read(self) -> None:
        """Idempotent — marking an already-read notification read again is a no-op."""
        if self.read_at is None:
            self.read_at = datetime.now(UTC)

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def __repr__(self) -> str:
        return f"<Notification id={self.id} recipient={self.recipient_user_id} read={self.is_read}>"
