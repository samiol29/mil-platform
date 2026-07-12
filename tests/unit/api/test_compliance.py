"""Unit tests for Security & Compliance API endpoints (spec 005 §16, Wave 4)."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient  # noqa: TC002

from mil.compliance.models import DataRetentionPolicy
from mil.kernel.errors import AuthorizationError, ValidationError


class TestListRetentionPolicies:
    def test_returns_200(self, client: TestClient, mock_compliance_workspace: MagicMock) -> None:
        policy = DataRetentionPolicy.create(
            tenant_id=uuid4(), data_category="DOCUMENT", retention_period_days=365, action="ARCHIVE"
        )
        mock_compliance_workspace.get_retention_policies.return_value = [policy]
        response = client.get("/v1/compliance/retention-policies")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1

    def test_readonly_role_returns_403(
        self, client: TestClient, mock_compliance_workspace: MagicMock
    ) -> None:
        mock_compliance_workspace.get_retention_policies.side_effect = AuthorizationError(
            "Permission denied: 'read:compliance' is required"
        )
        response = client.get("/v1/compliance/retention-policies")
        assert response.status_code == 403


class TestSetRetentionPolicy:
    def test_returns_200(self, client: TestClient, mock_compliance_workspace: MagicMock) -> None:
        policy = DataRetentionPolicy.create(
            tenant_id=uuid4(), data_category="DOCUMENT", retention_period_days=365, action="ARCHIVE"
        )
        mock_compliance_workspace.set_retention_policy.return_value = policy
        response = client.put(
            "/v1/compliance/retention-policies",
            json={"data_category": "DOCUMENT", "retention_period_days": 365, "action": "ARCHIVE"},
        )
        assert response.status_code == 200
        assert response.json()["action"] == "ARCHIVE"

    def test_delete_on_audit_event_returns_422(
        self, client: TestClient, mock_compliance_workspace: MagicMock
    ) -> None:
        mock_compliance_workspace.set_retention_policy.side_effect = ValidationError(
            "DELETE is not permitted for AUDIT_EVENT", field="action"
        )
        response = client.put(
            "/v1/compliance/retention-policies",
            json={"data_category": "AUDIT_EVENT", "retention_period_days": 90, "action": "DELETE"},
        )
        assert response.status_code == 422

    def test_invalid_action_rejected_by_schema(self, client: TestClient) -> None:
        response = client.put(
            "/v1/compliance/retention-policies",
            json={"data_category": "DOCUMENT", "retention_period_days": 90, "action": "OBLITERATE"},
        )
        assert response.status_code == 422

    def test_readonly_role_returns_403(
        self, client: TestClient, mock_compliance_workspace: MagicMock
    ) -> None:
        mock_compliance_workspace.set_retention_policy.side_effect = AuthorizationError(
            "Permission denied: 'manage:compliance' is required"
        )
        response = client.put(
            "/v1/compliance/retention-policies",
            json={"data_category": "DOCUMENT", "retention_period_days": 365, "action": "ARCHIVE"},
        )
        assert response.status_code == 403


class TestGetAccessLog:
    def test_returns_200(self, client: TestClient, mock_compliance_workspace: MagicMock) -> None:
        entry = MagicMock()
        entry.event_type = "APPLICATION_STATE_CHANGED"
        entry.actor_id = uuid4()
        entry.actor_type = "USER"
        from datetime import UTC, datetime

        entry.occurred_at = datetime.now(UTC)
        mock_compliance_workspace.get_access_log.return_value = [entry]
        response = client.get(
            "/v1/compliance/access-log",
            params={
                "application_id": str(uuid4()),
                "from_date": "2026-01-01T00:00:00Z",
                "to_date": "2026-02-01T00:00:00Z",
            },
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1

    def test_readonly_role_returns_403(
        self, client: TestClient, mock_compliance_workspace: MagicMock
    ) -> None:
        mock_compliance_workspace.get_access_log.side_effect = AuthorizationError(
            "Permission denied: 'read:compliance' is required"
        )
        response = client.get(
            "/v1/compliance/access-log",
            params={
                "application_id": str(uuid4()),
                "from_date": "2026-01-01T00:00:00Z",
                "to_date": "2026-02-01T00:00:00Z",
            },
        )
        assert response.status_code == 403
