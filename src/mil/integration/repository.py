"""Persistence gateway for the Integration Gateway bounded context."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from mil.integration.models import LOSConnection, LOSSyncEvent

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session


class IntegrationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_connection(self, connection: LOSConnection) -> None:
        self._session.add(connection)
        self._session.flush()

    def get_connection_by_id(self, connection_id: UUID) -> LOSConnection | None:
        return self._session.get(LOSConnection, connection_id)

    def get_connections_for_tenant(self, tenant_id: UUID) -> list[LOSConnection]:
        stmt = select(LOSConnection).where(LOSConnection.tenant_id == tenant_id)
        return list(self._session.scalars(stmt))

    def save_sync_event(self, event: LOSSyncEvent) -> None:
        self._session.add(event)
        self._session.flush()

    def get_sync_events_for_application(self, application_id: UUID) -> list[LOSSyncEvent]:
        stmt = (
            select(LOSSyncEvent)
            .where(LOSSyncEvent.application_id == application_id)
            .order_by(LOSSyncEvent.occurred_at.desc())
        )
        return list(self._session.scalars(stmt))

    def get_failed_sync_events_for_tenant(self, tenant_id: UUID) -> list[LOSSyncEvent]:
        stmt = (
            select(LOSSyncEvent)
            .where(LOSSyncEvent.tenant_id == tenant_id, LOSSyncEvent.outcome == "FAILURE")
            .order_by(LOSSyncEvent.occurred_at.desc())
        )
        return list(self._session.scalars(stmt))
