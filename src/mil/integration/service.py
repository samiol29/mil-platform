"""
IntegrationService — use-case orchestrator for the Integration Gateway
bounded context (spec 005-enterprise-platform §2, Wave 2).

Wraps the pre-existing ``mil.kernel.providers.los_adapter.LOSAdapter``
interface (already fully defined, already conformance-tested, already
registered via the DI container — see ``tests/providers/
test_los_adapter_conformance.py`` and ``src/providers/los/mock_los.py``) —
this service does not redefine adapter behaviour, it records what happened
when the adapter is called and enforces RBAC/audit around it.

Constitution Principle VI (Integration Model: read → enrich → return): MIL
never autonomously writes application state into a LOS.
``notify_readiness`` is the adapter's only write-direction method, and
``push_readiness`` below only ever calls it in direct response to an
explicit, human-triggered HTTP request — never from a background job.

Every sync/push emits a real ``AuditEvent`` via the shared ``AuditWriter``
(spec's own instruction: integrate with existing audit events, not a
duplicate model) *and* an ``LOSSyncEvent`` row carrying LOS-specific detail
the generic audit event schema doesn't (direction/outcome/adapter error
text) — see ``models.py``'s docstring for why both exist.

Dependency rule: imports from ``mil.integration``, ``mil.kernel``
(including ``mil.kernel.providers.los_adapter``, the kernel-defined
interface), and the Python standard library only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mil.integration.models import LOSConnection, LOSSyncEvent
from mil.kernel.errors import ProviderError
from mil.kernel.providers.los_adapter import ReadinessStatus
from mil.kernel.security import Permission, require_permission

if TYPE_CHECKING:
    from uuid import UUID

    from mil.audit.writer import AuditWriter
    from mil.integration.repository import IntegrationRepository
    from mil.kernel.providers.los_adapter import LOSAdapter
    from mil.kernel.security import AuthenticatedUser


class IntegrationService:
    def __init__(
        self, repository: IntegrationRepository, audit: AuditWriter, adapter: LOSAdapter
    ) -> None:
        self._repo = repository
        self._audit = audit
        self._adapter = adapter

    # ------------------------------------------------------------------
    # Connections (admin-facing configuration)
    # ------------------------------------------------------------------

    def create_connection(self, caller: AuthenticatedUser, *, vendor_type: str) -> LOSConnection:
        require_permission(caller, Permission.MANAGE_INTEGRATION)
        connection = LOSConnection.create(
            tenant_id=caller.tenant_id, vendor_type=vendor_type, created_by_user_id=caller.user_id
        )
        self._repo.save_connection(connection)
        self._audit.record(
            event_type="LOS_CONNECTION_CREATED",
            entity_type="LOS_CONNECTION",
            entity_id=connection.id,
            tenant_id=caller.tenant_id,
            actor_id=caller.user_id,
            event_data={"vendor_type": connection.vendor_type},
        )
        return connection

    def list_connections(self, caller: AuthenticatedUser) -> list[LOSConnection]:
        require_permission(caller, Permission.MANAGE_INTEGRATION)
        return self._repo.get_connections_for_tenant(caller.tenant_id)

    # ------------------------------------------------------------------
    # Sync (inbound read) / push (outbound notify) — the real LOSAdapter calls
    # ------------------------------------------------------------------

    def sync_application(
        self,
        caller: AuthenticatedUser,
        *,
        application_id: UUID,
        los_reference: str,
    ) -> LOSSyncEvent:
        """
        Pull the application's current state from the LOS
        (``LOSAdapter.read_application`` + ``read_documents``).

        Never raises on an adapter failure — records a FAILURE
        ``LOSSyncEvent`` with the adapter's real error message instead, so a
        sync failure is visible to Operations rather than silently dropped
        (spec's own "never a generic error, always the real message"
        discipline, carried over from the MVP's document-ingestion UX).
        """
        require_permission(caller, Permission.MANAGE_INTEGRATION)
        try:
            application_data = self._adapter.read_application(los_reference)
            documents = self._adapter.read_documents(los_reference)
            event = LOSSyncEvent.create(
                tenant_id=caller.tenant_id,
                application_id=application_id,
                direction="INBOUND",
                outcome="SUCCESS",
                initiated_by_user_id=caller.user_id,
                detail={
                    "application_type": application_data.application_type,
                    "document_count": len(documents),
                },
            )
        except ProviderError as exc:
            event = LOSSyncEvent.create(
                tenant_id=caller.tenant_id,
                application_id=application_id,
                direction="INBOUND",
                outcome="FAILURE",
                initiated_by_user_id=caller.user_id,
                error_message=str(exc),
            )
        self._repo.save_sync_event(event)
        self._audit.record(
            event_type="LOS_SYNC_ATTEMPTED",
            entity_type="LOS_SYNC_EVENT",
            entity_id=event.id,
            tenant_id=caller.tenant_id,
            application_id=application_id,
            actor_id=caller.user_id,
            event_data={"direction": "INBOUND", "outcome": event.outcome},
        )
        return event

    def push_readiness(
        self,
        caller: AuthenticatedUser,
        *,
        application_id: UUID,
        los_reference: str,
        is_ready: bool,
        summary: str,
        missing_items: tuple[str, ...] = (),
    ) -> LOSSyncEvent:
        """
        Notify the LOS of a Mortgage Readiness assessment
        (``LOSAdapter.notify_readiness``) — the adapter's only write-
        direction method, and only ever called here in direct response to an
        explicit human action (Principle VI: MIL never writes autonomously).
        """
        require_permission(caller, Permission.PUSH_LOS_STATUS)
        status = ReadinessStatus(
            los_reference=los_reference,
            is_ready=is_ready,
            summary=summary,
            missing_items=missing_items,
        )
        try:
            self._adapter.notify_readiness(los_reference, status)
            event = LOSSyncEvent.create(
                tenant_id=caller.tenant_id,
                application_id=application_id,
                direction="OUTBOUND",
                outcome="SUCCESS",
                initiated_by_user_id=caller.user_id,
                detail={"is_ready": is_ready, "summary": summary},
            )
        except ProviderError as exc:
            event = LOSSyncEvent.create(
                tenant_id=caller.tenant_id,
                application_id=application_id,
                direction="OUTBOUND",
                outcome="FAILURE",
                initiated_by_user_id=caller.user_id,
                error_message=str(exc),
            )
        self._repo.save_sync_event(event)
        self._audit.record(
            event_type="LOS_PUSH_ATTEMPTED",
            entity_type="LOS_SYNC_EVENT",
            entity_id=event.id,
            tenant_id=caller.tenant_id,
            application_id=application_id,
            actor_id=caller.user_id,
            event_data={"direction": "OUTBOUND", "outcome": event.outcome},
        )
        return event

    def get_sync_events(
        self, caller: AuthenticatedUser, application_id: UUID
    ) -> list[LOSSyncEvent]:
        require_permission(caller, Permission.MANAGE_INTEGRATION)
        return self._repo.get_sync_events_for_application(application_id)

    def get_failed_sync_events(self, caller: AuthenticatedUser) -> list[LOSSyncEvent]:
        require_permission(caller, Permission.MANAGE_INTEGRATION)
        return self._repo.get_failed_sync_events_for_tenant(caller.tenant_id)
