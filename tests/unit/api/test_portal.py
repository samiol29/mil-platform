"""Unit tests for Customer Portal (external-facing) API endpoints (spec 005 §12, Wave 4)."""

from __future__ import annotations

from unittest.mock import MagicMock  # noqa: TC003
from uuid import uuid4

from fastapi.testclient import TestClient  # noqa: TC002

from mil.kernel.errors import AuthenticationError, NotFoundError
from mil.portal.models import DocumentChecklistItem


def _make_item(application_id: object | None = None) -> DocumentChecklistItem:
    return DocumentChecklistItem.create(
        tenant_id=uuid4(),
        application_id=application_id or uuid4(),
        label="Bank statement",
        document_type="BANK_STATEMENT",
        requested_by_user_id=uuid4(),
    )


class TestActivate:
    def test_returns_200(self, client: TestClient, mock_portal_workspace: MagicMock) -> None:
        mock_portal_workspace.activate_account.return_value = "portal.abc.def"
        response = client.post(
            "/v1/portal/auth/activate", json={"party_id": str(uuid4()), "token": "raw-token"}
        )
        assert response.status_code == 200
        assert response.json()["session_token"] == "portal.abc.def"

    def test_invalid_token_returns_401(
        self, client: TestClient, mock_portal_workspace: MagicMock
    ) -> None:
        mock_portal_workspace.activate_account.side_effect = AuthenticationError(
            "Invalid or expired activation token"
        )
        response = client.post(
            "/v1/portal/auth/activate", json={"party_id": str(uuid4()), "token": "wrong-token"}
        )
        assert response.status_code == 401


class TestGetChecklist:
    def test_returns_200_without_internal_bearer(
        self, client: TestClient, mock_portal_workspace: MagicMock
    ) -> None:
        """Proves the portal route works via CurrentPortalClaims override, never CurrentUser."""
        item = _make_item()
        mock_portal_workspace.get_checklist_for_claims.return_value = [item]
        response = client.get("/v1/portal/checklist")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1

    def test_not_found_returns_404(self, client: TestClient, mock_portal_workspace: MagicMock) -> None:
        mock_portal_workspace.get_checklist_for_claims.side_effect = NotFoundError(
            "Party", uuid4()
        )
        response = client.get("/v1/portal/checklist")
        assert response.status_code == 404


class TestGetStatus:
    def test_returns_borrower_safe_label(
        self, client: TestClient, mock_portal_workspace: MagicMock
    ) -> None:
        application = MagicMock()
        application.status = "IN_REVIEW"
        mock_portal_workspace.get_status_for_claims.return_value = application
        response = client.get("/v1/portal/status")
        assert response.status_code == 200
        assert response.json()["status_label"] == "Documents under review"
        # Never the raw internal enum value leaked verbatim.
        assert "IN_REVIEW" not in response.text


class TestUploadForChecklistItem:
    def test_returns_200(self, client: TestClient, mock_portal_workspace: MagicMock) -> None:
        item = _make_item()
        item.fulfill(uuid4())
        mock_portal_workspace.upload_for_claims.return_value = item
        response = client.post(
            f"/v1/portal/checklist/{item.id}/upload",
            files={"file": ("statement.pdf", b"%PDF-1.4 fake content", "application/pdf")},
            data={"document_type": "BANK_STATEMENT"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "RECEIVED"

    def test_item_not_found_returns_404(
        self, client: TestClient, mock_portal_workspace: MagicMock
    ) -> None:
        mock_portal_workspace.upload_for_claims.side_effect = NotFoundError(
            "DocumentChecklistItem", uuid4()
        )
        response = client.post(
            f"/v1/portal/checklist/{uuid4()}/upload",
            files={"file": ("statement.pdf", b"content", "application/pdf")},
            data={"document_type": "BANK_STATEMENT"},
        )
        assert response.status_code == 404


class TestNoAuthReturns401:
    def test_missing_bearer_token_returns_401(self, client: TestClient) -> None:
        """
        Confirms the portal auth dependency is real (not bypassed): remove
        the override and hit a portal route with no Authorization header.
        """
        from main import create_app
        from mil.api.deps import get_current_user

        app = create_app()
        # Deliberately leave get_current_portal_claims un-overridden — only
        # override the internal-user dependency, proving a portal route
        # still demands its own, separate authentication.
        app.dependency_overrides[get_current_user] = lambda: None
        from fastapi.testclient import TestClient as _TestClient

        bare_client = _TestClient(app, raise_server_exceptions=True)
        response = bare_client.get("/v1/portal/checklist")
        assert response.status_code == 401
