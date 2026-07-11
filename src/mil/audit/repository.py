"""
Read-only persistence gateway for the Audit & Governance bounded context.

``AuditRepository`` complements ``AuditWriter`` (write-only) with the
query side needed to render a chronological audit trail for one
application (``GET /v1/applications/{id}/audit`` — spec 002 FR-035,
Constitution Principle VIII). It never writes: every ``AuditEvent`` row is
append-only and owned exclusively by ``AuditWriter``.

Dependency rule: imports only from ``mil.audit.models``, ``mil.kernel``, and
the Python standard library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from mil.audit.models import AuditEvent

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from sqlalchemy.orm import Session


class AuditRepository:
    """Read-only gateway for ``AuditEvent`` rows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, event_id: UUID) -> AuditEvent | None:
        """
        Return a single audit event by id (spec 005-enterprise-platform §13,
        Wave 2 — used to resolve a ``Notification``'s referenced event for
        display, without duplicating its data).
        """
        return self._session.get(AuditEvent, event_id)

    def get_for_application(self, application_id: UUID) -> list[AuditEvent]:
        """
        Return every audit event for an application in true chronological
        order.

        Ordered by ``sequence_number`` (the monotonic, gap-detectable
        database sequence) rather than ``occurred_at`` — this is the
        authoritative ordering for an append-only log, immune to clock
        skew between events recorded in rapid succession.
        """
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.application_id == application_id)
            .order_by(AuditEvent.sequence_number.asc())
        )
        return list(self._session.scalars(stmt))

    def get_for_application_in_range(
        self, application_id: UUID, *, from_date: datetime, to_date: datetime
    ) -> list[AuditEvent]:
        """
        Return an application's audit events within ``[from_date, to_date]``
        (spec 005-enterprise-platform §16, Wave 4 — Security & Compliance's
        access-log report, FR-SEC-003). Built directly on the existing
        append-only ``AuditEvent`` table — no new parallel logging
        mechanism, exactly as the spec requires.
        """
        stmt = (
            select(AuditEvent)
            .where(
                AuditEvent.application_id == application_id,
                AuditEvent.occurred_at >= from_date,
                AuditEvent.occurred_at <= to_date,
            )
            .order_by(AuditEvent.sequence_number.asc())
        )
        return list(self._session.scalars(stmt))
