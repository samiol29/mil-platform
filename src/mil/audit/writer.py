"""
Append-only audit event writer for the Audit & Governance bounded context.

``AuditWriter`` is the only mechanism through which bounded contexts emit
audit events. It writes ``AuditEvent`` records within the caller's existing
database session, ensuring that audit events are committed atomically with
the domain changes that triggered them.

Design contract:
- Audit events are written in the same transaction as the domain change.
  If the domain change rolls back, the audit event rolls back with it.
- ``record()`` never raises on constraint violations or duplicate IDs —
  the UUID PK guarantees uniqueness, and the caller controls the session.
- The ``sequence_number`` is assigned by the database on INSERT. The writer
  does not set it.
- ``actor_type`` defaults to "USER" when ``actor_id`` is provided; "SYSTEM"
  when it is None. Callers may override this for service account events.

Usage::

    writer = AuditWriter(session)
    writer.record(
        event_type="APPLICATION_CREATED",
        entity_type="APPLICATION",
        entity_id=application.id,
        tenant_id=application.tenant_id,
        application_id=application.id,
        actor_id=user.user_id,
        event_data={"status": "DRAFT"},
    )

Dependency rule: imports only from ``mil.kernel`` and ``mil.audit.models``.
No other bounded context may be imported here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from mil.audit.models import AuditEvent
from mil.kernel.metrics import MetricName

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session

    from mil.kernel.observability import MetricEmitter


class AuditWriter:
    """
    Writes immutable audit records within an active database session.

    The session is owned by the caller (typically a repository or service). The
    writer does not commit or rollback — that responsibility belongs to the
    caller's unit of work.

    Inject ``AuditWriter`` into repositories and services that need to emit
    audit events. Never instantiate it directly in domain entities.

    ``metrics`` (Sprint 8 — Production Hardening) is optional: when supplied,
    every ``record()`` call increments ``audit.events.total`` on it, giving
    ``GET /v1/metrics`` basic visibility into audit volume. Callers that omit
    it (the default) are unaffected — audit writing itself never depends on
    metrics being configured.
    """

    def __init__(self, session: Session, metrics: MetricEmitter | None = None) -> None:
        self._session = session
        self._metrics = metrics

    def record(
        self,
        *,
        event_type: str,
        entity_type: str,
        entity_id: UUID,
        tenant_id: UUID,
        application_id: UUID | None = None,
        actor_id: UUID | None = None,
        actor_type: str | None = None,
        event_data: dict[str, object] | None = None,
    ) -> AuditEvent:
        """
        Append a single audit event to the session.

        The event is flushed with the next session flush (which may happen
        automatically before a query, or explicitly via ``session.flush()``).

        Args:
            event_type: One of the ``AuditEventType`` string constants from
                ``data-model.md`` (e.g. ``"APPLICATION_CREATED"``).
            entity_type: The domain entity category (e.g. ``"APPLICATION"``).
            entity_id: The UUID of the affected entity.
            tenant_id: The tenant context in which the event occurred.
            application_id: Associated application UUID for lifecycle
                correlation queries. May be None for cross-application events.
            actor_id: UUID of the authenticated user who triggered the event.
                None for system-driven events.
            actor_type: ``"USER"`` or ``"SYSTEM"``. Defaults to ``"USER"``
                when ``actor_id`` is provided, ``"SYSTEM"`` otherwise.
            event_data: Event-specific payload as a plain dict. Must be
                JSON-serialisable.

        Returns:
            The ``AuditEvent`` ORM instance, already added to the session.
        """
        resolved_actor_type: str
        if actor_type is not None:
            resolved_actor_type = actor_type
        elif actor_id is not None:
            resolved_actor_type = "USER"
        else:
            resolved_actor_type = "SYSTEM"

        event = AuditEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            application_id=application_id,
            actor_id=actor_id,
            actor_type=resolved_actor_type,
            event_data=event_data or {},
            occurred_at=datetime.now(UTC),
        )
        self._session.add(event)
        if self._metrics is not None:
            self._metrics.increment(MetricName.AUDIT_EVENTS_TOTAL)
        return event
