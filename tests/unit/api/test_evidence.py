"""Unit tests for Evidence API endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock  # noqa: TC003

from fastapi.testclient import TestClient  # noqa: TC002

from mil.kernel.errors import AuthorizationError
from tests.unit.api.conftest import TEST_APP_ID, make_evidence_item


class TestListEvidence:
    def test_returns_200(self, client: TestClient, mock_evidence_service: MagicMock) -> None:
        mock_evidence_service.list_for_application.return_value = [make_evidence_item()]
        response = client.get(f"/v1/applications/{TEST_APP_ID}/evidence")
        assert response.status_code == 200

    def test_returns_evidence_fields(
        self, client: TestClient, mock_evidence_service: MagicMock
    ) -> None:
        item = make_evidence_item()
        mock_evidence_service.list_for_application.return_value = [item]
        data = client.get(f"/v1/applications/{TEST_APP_ID}/evidence").json()
        assert len(data) == 1
        assert data[0]["id"] == str(item.id)
        assert data[0]["document_id"] == str(item.document_id)
        assert data[0]["confidence"] == "high"
        assert data[0]["extraction_method"] == "mock-keyword-matcher"
        assert data[0]["page_number"] == 2

    def test_empty_list(self, client: TestClient, mock_evidence_service: MagicMock) -> None:
        mock_evidence_service.list_for_application.return_value = []
        data = client.get(f"/v1/applications/{TEST_APP_ID}/evidence").json()
        assert data == []

    def test_authorization_error_returns_403(
        self, client: TestClient, mock_evidence_service: MagicMock
    ) -> None:
        mock_evidence_service.list_for_application.side_effect = AuthorizationError(
            "Permission denied: 'read:evidence' is required"
        )
        response = client.get(f"/v1/applications/{TEST_APP_ID}/evidence")
        assert response.status_code == 403
