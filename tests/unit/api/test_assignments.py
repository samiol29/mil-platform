"""Unit tests for Assignment API endpoints (spec 005 §1, Wave 2)."""

from __future__ import annotations

from unittest.mock import MagicMock  # noqa: TC003
from uuid import uuid4

from fastapi.testclient import TestClient  # noqa: TC002

from mil.assignment.models import Assignment
from mil.kernel.errors import AuthorizationError
from tests.unit.api.conftest import make_application


class TestSetAssignment:
    def test_returns_200(self, client: TestClient, mock_assignment_service: MagicMock) -> None:
        app_id = uuid4()
        owner = uuid4()
        assignment = Assignment.create(
            application_id=app_id, owner_user_id=owner, assigned_by_user_id=uuid4()
        )
        mock_assignment_service.set_assignment.return_value = assignment
        response = client.put(
            f"/v1/applications/{app_id}/assignment", json={"owner_user_id": str(owner)}
        )
        assert response.status_code == 200
        assert response.json()["owner_user_id"] == str(owner)

    def test_readonly_role_returns_403(
        self, client: TestClient, mock_assignment_service: MagicMock
    ) -> None:
        mock_assignment_service.set_assignment.side_effect = AuthorizationError(
            "Permission denied: 'manage:assignment' is required"
        )
        response = client.put(
            f"/v1/applications/{uuid4()}/assignment", json={"owner_user_id": str(uuid4())}
        )
        assert response.status_code == 403


class TestGetAssignment:
    def test_returns_null_when_none_exists(
        self, client: TestClient, mock_assignment_service: MagicMock
    ) -> None:
        mock_assignment_service.get_assignment.return_value = None
        response = client.get(f"/v1/applications/{uuid4()}/assignment")
        assert response.status_code == 200
        assert response.json() is None


class TestPortfolio:
    def test_returns_owned_applications(
        self, client: TestClient, mock_rm_workspace: MagicMock
    ) -> None:
        mock_rm_workspace.get_portfolio.return_value = [make_application()]
        response = client.get("/v1/rm/portfolio")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1
