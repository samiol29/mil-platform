"""Unit tests for Document Checklist (internal-facing) API endpoints (spec 005 §12, Wave 4)."""

from __future__ import annotations

from unittest.mock import MagicMock  # noqa: TC003
from uuid import uuid4

from fastapi.testclient import TestClient  # noqa: TC002

from mil.kernel.errors import AuthorizationError
from mil.portal.models import DocumentChecklistItem, PortalAccount


def _make_item() -> DocumentChecklistItem:
    return DocumentChecklistItem.create(
        tenant_id=uuid4(),
        application_id=uuid4(),
        label="Bank statement",
        document_type="BANK_STATEMENT",
        requested_by_user_id=uuid4(),
    )


class TestCreateChecklistItem:
    def test_returns_200(self, client: TestClient, mock_portal_workspace: MagicMock) -> None:
        item = _make_item()
        mock_portal_workspace.create_checklist_item.return_value = item
        response = client.post(
            f"/v1/applications/{item.application_id}/checklist-items",
            json={"label": "Bank statement", "document_type": "BANK_STATEMENT"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "REQUESTED"

    def test_readonly_role_returns_403(
        self, client: TestClient, mock_portal_workspace: MagicMock
    ) -> None:
        mock_portal_workspace.create_checklist_item.side_effect = AuthorizationError(
            "Permission denied: 'manage:checklist' is required"
        )
        response = client.post(
            f"/v1/applications/{uuid4()}/checklist-items",
            json={"label": "Bank statement", "document_type": "BANK_STATEMENT"},
        )
        assert response.status_code == 403


class TestListChecklistItems:
    def test_returns_200(self, client: TestClient, mock_portal_workspace: MagicMock) -> None:
        item = _make_item()
        mock_portal_workspace.get_checklist_for_application.return_value = [item]
        response = client.get(f"/v1/applications/{item.application_id}/checklist-items")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1


class TestWaiveChecklistItem:
    def test_returns_200(self, client: TestClient, mock_portal_workspace: MagicMock) -> None:
        item = _make_item()
        item.waive()
        mock_portal_workspace.waive_item.return_value = item
        response = client.post(
            f"/v1/applications/{item.application_id}/checklist-items/{item.id}/waive"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "WAIVED"


class TestInviteBorrower:
    def test_returns_200(self, client: TestClient, mock_portal_workspace: MagicMock) -> None:
        account, raw_token = PortalAccount.invite(
            tenant_id=uuid4(), party_id=uuid4(), email_hash="hash123"
        )
        mock_portal_workspace.invite_borrower.return_value = (account, raw_token)
        response = client.post(
            f"/v1/applications/{uuid4()}/checklist-items/{uuid4()}/invite-borrower",
            json={"party_id": str(account.party_id), "email": "borrower@example.com"},
        )
        assert response.status_code == 200
        assert response.json()["activation_token"] == raw_token
        assert response.json()["status"] == "INVITED"

    def test_readonly_role_returns_403(
        self, client: TestClient, mock_portal_workspace: MagicMock
    ) -> None:
        mock_portal_workspace.invite_borrower.side_effect = AuthorizationError(
            "Permission denied: 'manage:checklist' is required"
        )
        response = client.post(
            f"/v1/applications/{uuid4()}/checklist-items/{uuid4()}/invite-borrower",
            json={"party_id": str(uuid4()), "email": "borrower@example.com"},
        )
        assert response.status_code == 403
