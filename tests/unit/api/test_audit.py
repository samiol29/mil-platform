"""Unit tests for Audit API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock  # noqa: TC003
from uuid import uuid4

from fastapi.testclient import TestClient  # noqa: TC002

from mil.audit.models import AuditEvent
from tests.unit.api.conftest import TEST_APP_ID


def _make_event(**overrides: object) -> AuditEvent:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "tenant_id": uuid4(),
        "event_type": "APPLICATION_CREATED",
        "entity_type": "APPLICATION",
        "entity_id": uuid4(),
        "application_id": TEST_APP_ID,
        "actor_type": "SYSTEM",
        "event_data": {},
        "occurred_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return AuditEvent(**defaults)  # type: ignore[arg-type]


class TestGetAuditTrail:
    def test_returns_200(self, client: TestClient, mock_audit_repository: MagicMock) -> None:
        mock_audit_repository.get_for_application.return_value = [_make_event()]
        response = client.get(f"/v1/applications/{TEST_APP_ID}/audit")
        assert response.status_code == 200

    def test_returns_event_fields(
        self, client: TestClient, mock_audit_repository: MagicMock
    ) -> None:
        event = _make_event(event_type="EVIDENCE_CREATED")
        mock_audit_repository.get_for_application.return_value = [event]
        data = client.get(f"/v1/applications/{TEST_APP_ID}/audit").json()
        assert len(data) == 1
        assert data[0]["event_type"] == "EVIDENCE_CREATED"
        assert data[0]["application_id"] == str(TEST_APP_ID)

    def test_empty_trail(self, client: TestClient, mock_audit_repository: MagicMock) -> None:
        mock_audit_repository.get_for_application.return_value = []
        data = client.get(f"/v1/applications/{TEST_APP_ID}/audit").json()
        assert data == []
