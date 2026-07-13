"""Unit tests for mil.integration.service — IntegrationService.

Uses the same real ``MockLOSAdapter`` (``src/providers/los/mock_los.py``)
the conformance test suite validates — not a bespoke fake — plus one
purpose-built failing adapter to exercise the honest-failure path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from mil.integration.service import IntegrationService
from mil.kernel.errors import AuthorizationError, ProviderError
from mil.kernel.providers.los_adapter import ApplicationData, LOSAdapter, ReadinessStatus
from mil.kernel.security import AuthenticatedUser, Role
from providers.los.mock_los import MockLOSAdapter

if TYPE_CHECKING:
    from mil.integration.models import LOSConnection, LOSSyncEvent


class AlwaysFailingLOSAdapter(LOSAdapter):
    def read_application(self, los_reference: str) -> ApplicationData:
        raise ProviderError("LOS is unavailable", provider_name="test-los")

    def read_documents(self, los_reference: str) -> list:  # type: ignore[type-arg]
        raise ProviderError("LOS is unavailable", provider_name="test-los")

    def notify_readiness(self, los_reference: str, status: ReadinessStatus) -> None:
        raise ProviderError("LOS rejected the notification", provider_name="test-los")


class FakeIntegrationRepository:
    def __init__(self) -> None:
        self.connections: list[LOSConnection] = []
        self.sync_events: list[LOSSyncEvent] = []

    def save_connection(self, connection: LOSConnection) -> None:
        self.connections.append(connection)

    def get_connections_for_tenant(self, tenant_id: object) -> list[LOSConnection]:
        return [c for c in self.connections if c.tenant_id == tenant_id]

    def save_sync_event(self, event: LOSSyncEvent) -> None:
        self.sync_events.append(event)

    def get_sync_events_for_application(self, application_id: object) -> list[LOSSyncEvent]:
        return [e for e in self.sync_events if e.application_id == application_id]

    def get_failed_sync_events_for_tenant(self, tenant_id: object) -> list[LOSSyncEvent]:
        return [e for e in self.sync_events if e.tenant_id == tenant_id and e.outcome == "FAILURE"]


class FakeAuditWriter:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record(self, **kwargs: object) -> object:
        self.records.append(kwargs)
        return object()


def _admin_caller(tenant_id: object) -> AuthenticatedUser:
    return AuthenticatedUser(user_id=uuid4(), tenant_id=tenant_id, roles=frozenset({Role.ADMIN}))


def _readonly_caller(tenant_id: object) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(), tenant_id=tenant_id, roles=frozenset({Role.AUDIT_TEAM})
    )


def _make_service(
    adapter: LOSAdapter,
) -> tuple[IntegrationService, FakeIntegrationRepository, FakeAuditWriter]:
    repo = FakeIntegrationRepository()
    audit = FakeAuditWriter()
    return IntegrationService(repo, audit, adapter), repo, audit  # type: ignore[arg-type]


class TestCreateConnection:
    def test_creates_connection(self) -> None:
        service, _repo, audit = _make_service(MockLOSAdapter())
        tenant_id = uuid4()
        caller = _admin_caller(tenant_id)

        connection = service.create_connection(caller, vendor_type="encompass")

        assert connection.vendor_type == "encompass"
        assert audit.records[-1]["event_type"] == "LOS_CONNECTION_CREATED"

    def test_readonly_role_forbidden(self) -> None:
        service, _, _ = _make_service(MockLOSAdapter())
        caller = _readonly_caller(uuid4())
        with pytest.raises(AuthorizationError):
            service.create_connection(caller, vendor_type="encompass")


class TestSyncApplication:
    def test_success_records_inbound_event(self) -> None:
        service, _repo, audit = _make_service(MockLOSAdapter())
        tenant_id = uuid4()
        caller = _admin_caller(tenant_id)
        app_id = uuid4()

        event = service.sync_application(caller, application_id=app_id, los_reference="LOS-REF-001")

        assert event.outcome == "SUCCESS"
        assert event.direction == "INBOUND"
        assert audit.records[-1]["event_type"] == "LOS_SYNC_ATTEMPTED"

    def test_adapter_failure_is_recorded_not_raised(self) -> None:
        service, _repo, _ = _make_service(AlwaysFailingLOSAdapter())
        caller = _admin_caller(uuid4())

        event = service.sync_application(
            caller, application_id=uuid4(), los_reference="LOS-REF-001"
        )

        assert event.outcome == "FAILURE"
        assert event.error_message == "LOS is unavailable"


class TestPushReadiness:
    def test_success_records_outbound_event(self) -> None:
        service, _repo, _audit = _make_service(MockLOSAdapter())
        tenant_id = uuid4()
        caller = _admin_caller(tenant_id)

        event = service.push_readiness(
            caller,
            application_id=uuid4(),
            los_reference="LOS-REF-001",
            is_ready=True,
            summary="Ready for underwriting",
        )

        assert event.outcome == "SUCCESS"
        assert event.direction == "OUTBOUND"

    def test_adapter_failure_is_recorded_not_raised(self) -> None:
        service, _, _ = _make_service(AlwaysFailingLOSAdapter())
        caller = _admin_caller(uuid4())

        event = service.push_readiness(
            caller,
            application_id=uuid4(),
            los_reference="LOS-REF-001",
            is_ready=False,
            summary="Missing documents",
        )

        assert event.outcome == "FAILURE"
        assert event.error_message == "LOS rejected the notification"
