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
    from uuid import UUID

    from sqlalchemy.orm import Session


class AuditRepository:
    """Read-only gateway for ``AuditEvent`` rows."""

    def __init__(self, session: Session) -> None:
        self._session = session

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
