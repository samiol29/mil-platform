"""Unit tests for LOS Integration API endpoints (spec 005 §2, Wave 2)."""

from __future__ import annotations

from unittest.mock import MagicMock  # noqa: TC003
from uuid import uuid4

from fastapi.testclient import TestClient  # noqa: TC002

from mil.integration.models import LOSConnection, LOSSyncEvent
from mil.kernel.errors import NotFoundError, ValidationError


class TestCreateConnection:
    def test_returns_201(self, client: TestClient, mock_integration_workspace: MagicMock) -> None:
        connection = LOSConnection.create(
            tenant_id=uuid4(), vendor_type="encompass", created_by_user_id=uuid4()
        )
        mock_integration_workspace.service.create_connection.return_value = connection
        response = client.post(
            "/v1/integrations/los/connections", json={"vendor_type": "encompass"}
        )
        assert response.status_code == 201
        assert response.json()["vendor_type"] == "encompass"


class TestSyncApplication:
    def test_returns_200(self, client: TestClient, mock_integration_workspace: MagicMock) -> None:
        event = LOSSyncEvent.create(
            tenant_id=uuid4(),
            application_id=uuid4(),
            direction="INBOUND",
            outcome="SUCCESS",
            initiated_by_user_id=uuid4(),
        )
        mock_integration_workspace.sync_application.return_value = event
        response = client.post(f"/v1/applications/{uuid4()}/los-sync")
        assert response.status_code == 200
        assert response.json()["outcome"] == "SUCCESS"

    def test_no_los_reference_returns_422(
        self, client: TestClient, mock_integration_workspace: MagicMock
    ) -> None:
        mock_integration_workspace.sync_application.side_effect = ValidationError(
            "Application has no los_reference set", field="los_reference"
        )
        response = client.post(f"/v1/applications/{uuid4()}/los-sync")
        assert response.status_code == 422

    def test_application_not_found_returns_404(
        self, client: TestClient, mock_integration_workspace: MagicMock
    ) -> None:
        mock_integration_workspace.sync_application.side_effect = NotFoundError(
            "Application", uuid4()
        )
        response = client.post(f"/v1/applications/{uuid4()}/los-sync")
        assert response.status_code == 404


class TestPushReadiness:
    def test_returns_200(self, client: TestClient, mock_integration_workspace: MagicMock) -> None:
        event = LOSSyncEvent.create(
            tenant_id=uuid4(),
            application_id=uuid4(),
            direction="OUTBOUND",
            outcome="SUCCESS",
            initiated_by_user_id=uuid4(),
        )
        mock_integration_workspace.push_readiness.return_value = event
        response = client.post(
            f"/v1/applications/{uuid4()}/los-push",
            json={"is_ready": True, "summary": "Ready for underwriting"},
        )
        assert response.status_code == 200
        assert response.json()["direction"] == "OUTBOUND"


class TestSyncFailureQueue:
    def test_returns_failed_events(
        self, client: TestClient, mock_integration_workspace: MagicMock
    ) -> None:
        event = LOSSyncEvent.create(
            tenant_id=uuid4(),
            application_id=uuid4(),
            direction="INBOUND",
            outcome="FAILURE",
            initiated_by_user_id=uuid4(),
            error_message="LOS is unavailable",
        )
        mock_integration_workspace.service.get_failed_sync_events.return_value = [event]
        response = client.get("/v1/integrations/los/sync-events")
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["error_message"] == "LOS is unavailable"
