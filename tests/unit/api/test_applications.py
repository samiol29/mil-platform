"""Unit tests for Application and Party API endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock  # noqa: TC003
from uuid import uuid4

from fastapi.testclient import TestClient  # noqa: TC002

from mil.application.models import ApplicationStatus
from mil.kernel.errors import (
    AuthorizationError,
    ConflictError,
    InvalidStateTransitionError,
    NotFoundError,
    ValidationError,
)
from mil.kernel.security import AuthenticatedUser  # noqa: TC001
from tests.unit.api.conftest import (
    TEST_APP_ID,
    make_application,
    make_party,
)

# ---------------------------------------------------------------------------
# POST /v1/applications
# ---------------------------------------------------------------------------


class TestCreateApplication:
    def test_returns_201(self, client: TestClient, mock_app_service: MagicMock) -> None:
        app = make_application()
        mock_app_service.create_application.return_value = app
        response = client.post("/v1/applications", json={"los_reference": "LOS-123"})
        assert response.status_code == 201

    def test_returns_application_response(
        self, client: TestClient, mock_app_service: MagicMock
    ) -> None:
        app = make_application()
        mock_app_service.create_application.return_value = app
        data = client.post("/v1/applications", json={}).json()
        assert "id" in data
        assert "status" in data
        assert data["status"] == ApplicationStatus.DRAFT

    def test_passes_los_reference(self, client: TestClient, mock_app_service: MagicMock) -> None:
        app = make_application(los_reference="LOS-999")
        mock_app_service.create_application.return_value = app
        client.post("/v1/applications", json={"los_reference": "LOS-999"})
        call_kwargs = mock_app_service.create_application.call_args.kwargs
        assert call_kwargs["los_reference"] == "LOS-999"

    def test_passes_loan_number(self, client: TestClient, mock_app_service: MagicMock) -> None:
        app = make_application(loan_number="LN-999")
        mock_app_service.create_application.return_value = app
        client.post("/v1/applications", json={"loan_number": "LN-999"})
        call_kwargs = mock_app_service.create_application.call_args.kwargs
        assert call_kwargs["loan_number"] == "LN-999"

    def test_returns_loan_number(self, client: TestClient, mock_app_service: MagicMock) -> None:
        app = make_application(loan_number="LN-999")
        mock_app_service.create_application.return_value = app
        data = client.post("/v1/applications", json={"loan_number": "LN-999"}).json()
        assert data["loan_number"] == "LN-999"

    def test_tenant_id_comes_from_authenticated_user(
        self, client: TestClient, mock_app_service: MagicMock, current_user: AuthenticatedUser
    ) -> None:
        app = make_application()
        mock_app_service.create_application.return_value = app
        client.post("/v1/applications", json={})
        call_kwargs = mock_app_service.create_application.call_args.kwargs
        # Tenant must come from the user, not from the request body
        assert str(call_kwargs["tenant_id"]) == str(current_user.tenant_id)

    def test_party_count_zero_for_new_app(
        self, client: TestClient, mock_app_service: MagicMock
    ) -> None:
        app = make_application()
        mock_app_service.create_application.return_value = app
        data = client.post("/v1/applications", json={}).json()
        assert data["party_count"] == 0

    def test_service_authorization_error_returns_403(
        self, client: TestClient, mock_app_service: MagicMock
    ) -> None:
        mock_app_service.create_application.side_effect = AuthorizationError(
            "Permission denied: 'write:application' is required"
        )
        response = client.post("/v1/applications", json={})
        assert response.status_code == 403

    def test_empty_body_is_accepted(self, client: TestClient, mock_app_service: MagicMock) -> None:
        app = make_application()
        mock_app_service.create_application.return_value = app
        response = client.post("/v1/applications", json={})
        assert response.status_code == 201


# ---------------------------------------------------------------------------
# GET /v1/applications
# ---------------------------------------------------------------------------


class TestListApplications:
    def test_returns_200(self, client: TestClient, mock_app_service: MagicMock) -> None:
        mock_app_service.list_applications.return_value = []
        response = client.get("/v1/applications")
        assert response.status_code == 200

    def test_returns_empty_list(self, client: TestClient, mock_app_service: MagicMock) -> None:
        mock_app_service.list_applications.return_value = []
        data = client.get("/v1/applications").json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_returns_applications(self, client: TestClient, mock_app_service: MagicMock) -> None:
        mock_app_service.list_applications.return_value = [
            make_application(),
            make_application(),
        ]
        data = client.get("/v1/applications").json()
        assert len(data["items"]) == 2
        assert data["total"] == 2

    def test_tenant_comes_from_user(
        self, client: TestClient, mock_app_service: MagicMock, current_user: AuthenticatedUser
    ) -> None:
        mock_app_service.list_applications.return_value = []
        client.get("/v1/applications")
        call_kwargs = mock_app_service.list_applications.call_args.kwargs
        assert str(call_kwargs["tenant_id"]) == str(current_user.tenant_id)

    def test_status_filter_passed_to_service(
        self, client: TestClient, mock_app_service: MagicMock
    ) -> None:
        mock_app_service.list_applications.return_value = []
        client.get("/v1/applications?status=DRAFT")
        call_kwargs = mock_app_service.list_applications.call_args.kwargs
        assert call_kwargs["status"] == "DRAFT"

    def test_pagination_echoed_in_response(
        self, client: TestClient, mock_app_service: MagicMock
    ) -> None:
        mock_app_service.list_applications.return_value = []
        data = client.get("/v1/applications?page=3&page_size=10").json()
        assert data["page"] == 3
        assert data["page_size"] == 10


# ---------------------------------------------------------------------------
# GET /v1/applications/{id}
# ---------------------------------------------------------------------------


class TestGetApplication:
    def test_returns_200(self, client: TestClient, mock_app_service: MagicMock) -> None:
        mock_app_service.get_application.return_value = make_application()
        response = client.get(f"/v1/applications/{TEST_APP_ID}")
        assert response.status_code == 200

    def test_returns_application_fields(
        self, client: TestClient, mock_app_service: MagicMock
    ) -> None:
        app = make_application()
        mock_app_service.get_application.return_value = app
        data = client.get(f"/v1/applications/{app.id}").json()
        assert data["id"] == str(app.id)
        assert data["status"] == app.status

    def test_not_found_returns_404(self, client: TestClient, mock_app_service: MagicMock) -> None:
        mock_app_service.get_application.side_effect = NotFoundError(
            "MortgageApplication", TEST_APP_ID
        )
        response = client.get(f"/v1/applications/{TEST_APP_ID}")
        assert response.status_code == 404

    def test_not_found_error_body(self, client: TestClient, mock_app_service: MagicMock) -> None:
        mock_app_service.get_application.side_effect = NotFoundError(
            "MortgageApplication", TEST_APP_ID
        )
        data = client.get(f"/v1/applications/{TEST_APP_ID}").json()
        assert data["code"] == "NOT_FOUND"
        assert "message" in data


# ---------------------------------------------------------------------------
# POST /v1/applications/{id}/submit
# ---------------------------------------------------------------------------


class TestSubmitApplication:
    def test_returns_200(self, client: TestClient, mock_app_service: MagicMock) -> None:
        app = make_application(status=ApplicationStatus.SUBMITTED)
        mock_app_service.submit_application.return_value = app
        response = client.post(f"/v1/applications/{TEST_APP_ID}/submit")
        assert response.status_code == 200

    def test_returns_updated_status(self, client: TestClient, mock_app_service: MagicMock) -> None:
        app = make_application(status=ApplicationStatus.SUBMITTED)
        mock_app_service.submit_application.return_value = app
        data = client.post(f"/v1/applications/{TEST_APP_ID}/submit").json()
        assert data["status"] == ApplicationStatus.SUBMITTED

    def test_invalid_transition_returns_422(
        self, client: TestClient, mock_app_service: MagicMock
    ) -> None:
        mock_app_service.submit_application.side_effect = InvalidStateTransitionError(
            "MortgageApplication", TEST_APP_ID, "WITHDRAWN", "SUBMITTED"
        )
        response = client.post(f"/v1/applications/{TEST_APP_ID}/submit")
        assert response.status_code == 422

    def test_conflict_no_applicant_returns_409(
        self, client: TestClient, mock_app_service: MagicMock
    ) -> None:
        mock_app_service.submit_application.side_effect = ConflictError(
            "Cannot submit: no APPLICANT party registered."
        )
        response = client.post(f"/v1/applications/{TEST_APP_ID}/submit")
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# POST /v1/applications/{id}/withdraw
# ---------------------------------------------------------------------------


class TestWithdrawApplication:
    def test_returns_200(self, client: TestClient, mock_app_service: MagicMock) -> None:
        app = make_application(status=ApplicationStatus.WITHDRAWN)
        mock_app_service.withdraw_application.return_value = app
        response = client.post(f"/v1/applications/{TEST_APP_ID}/withdraw")
        assert response.status_code == 200

    def test_returns_withdrawn_status(
        self, client: TestClient, mock_app_service: MagicMock
    ) -> None:
        app = make_application(status=ApplicationStatus.WITHDRAWN)
        mock_app_service.withdraw_application.return_value = app
        data = client.post(f"/v1/applications/{TEST_APP_ID}/withdraw").json()
        assert data["status"] == ApplicationStatus.WITHDRAWN

    def test_already_withdrawn_returns_422(
        self, client: TestClient, mock_app_service: MagicMock
    ) -> None:
        mock_app_service.withdraw_application.side_effect = InvalidStateTransitionError(
            "MortgageApplication", TEST_APP_ID, "WITHDRAWN", "WITHDRAWN"
        )
        response = client.post(f"/v1/applications/{TEST_APP_ID}/withdraw")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /v1/applications/{id}/parties
# ---------------------------------------------------------------------------


class TestAddParty:
    def test_returns_201(self, client: TestClient, mock_app_service: MagicMock) -> None:
        mock_app_service.add_party_by_type_string.return_value = make_party()
        response = client.post(
            f"/v1/applications/{TEST_APP_ID}/parties",
            json={"party_type": "APPLICANT", "display_name": "Primary Borrower"},
        )
        assert response.status_code == 201

    def test_returns_party_fields(self, client: TestClient, mock_app_service: MagicMock) -> None:
        party = make_party()
        mock_app_service.add_party_by_type_string.return_value = party
        data = client.post(
            f"/v1/applications/{TEST_APP_ID}/parties",
            json={"party_type": "APPLICANT", "display_name": "Primary Borrower"},
        ).json()
        assert data["party_type"] == "APPLICANT"
        assert data["display_name"] == "Primary Borrower"
        assert "id" in data
        assert "created_at" in data

    def test_passes_party_type_and_name_to_service(
        self, client: TestClient, mock_app_service: MagicMock
    ) -> None:
        mock_app_service.add_party_by_type_string.return_value = make_party()
        client.post(
            f"/v1/applications/{TEST_APP_ID}/parties",
            json={"party_type": "GUARANTOR", "display_name": "Guarantor A"},
        )
        call_kwargs = mock_app_service.add_party_by_type_string.call_args.kwargs
        assert call_kwargs["party_type_str"] == "GUARANTOR"
        assert call_kwargs["display_name"] == "Guarantor A"

    def test_missing_party_type_returns_422(self, client: TestClient) -> None:
        response = client.post(
            f"/v1/applications/{TEST_APP_ID}/parties",
            json={"display_name": "Borrower"},
        )
        assert response.status_code == 422

    def test_missing_display_name_returns_422(self, client: TestClient) -> None:
        response = client.post(
            f"/v1/applications/{TEST_APP_ID}/parties",
            json={"party_type": "APPLICANT"},
        )
        assert response.status_code == 422

    def test_invalid_party_type_returns_422(
        self, client: TestClient, mock_app_service: MagicMock
    ) -> None:
        mock_app_service.add_party_by_type_string.side_effect = ValidationError(
            "Invalid party type 'ALIEN'.", field="party_type"
        )
        response = client.post(
            f"/v1/applications/{TEST_APP_ID}/parties",
            json={"party_type": "ALIEN", "display_name": "Unknown"},
        )
        assert response.status_code == 422

    def test_application_not_found_returns_404(
        self, client: TestClient, mock_app_service: MagicMock
    ) -> None:
        mock_app_service.add_party_by_type_string.side_effect = NotFoundError(
            "MortgageApplication", TEST_APP_ID
        )
        response = client.post(
            f"/v1/applications/{TEST_APP_ID}/parties",
            json={"party_type": "APPLICANT", "display_name": "B"},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /v1/applications/{id}/parties/{party_id}
# ---------------------------------------------------------------------------


class TestRemoveParty:
    def test_returns_204(self, client: TestClient, mock_app_service: MagicMock) -> None:
        mock_app_service.remove_party.return_value = None
        response = client.delete(f"/v1/applications/{TEST_APP_ID}/parties/{uuid4()}")
        assert response.status_code == 204

    def test_not_found_returns_404(self, client: TestClient, mock_app_service: MagicMock) -> None:
        mock_app_service.remove_party.side_effect = NotFoundError("Party", uuid4())
        response = client.delete(f"/v1/applications/{TEST_APP_ID}/parties/{uuid4()}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /v1/applications/{id}/parties
# ---------------------------------------------------------------------------


class TestListParties:
    def test_returns_200(self, client: TestClient, mock_app_service: MagicMock) -> None:
        app = make_application()
        mock_app_service.get_application.return_value = app
        response = client.get(f"/v1/applications/{TEST_APP_ID}/parties")
        assert response.status_code == 200

    def test_returns_empty_list_when_no_parties(
        self, client: TestClient, mock_app_service: MagicMock
    ) -> None:
        app = make_application()
        mock_app_service.get_application.return_value = app
        data = client.get(f"/v1/applications/{TEST_APP_ID}/parties").json()
        assert data == []

    def test_returns_party_list(self, client: TestClient, mock_app_service: MagicMock) -> None:
        party = make_party()
        app = make_application()
        app.parties.append(party)
        mock_app_service.get_application.return_value = app
        data = client.get(f"/v1/applications/{TEST_APP_ID}/parties").json()
        assert len(data) == 1
        assert data[0]["party_type"] == "APPLICANT"

    def test_not_found_returns_404(self, client: TestClient, mock_app_service: MagicMock) -> None:
        mock_app_service.get_application.side_effect = NotFoundError(
            "MortgageApplication", TEST_APP_ID
        )
        response = client.get(f"/v1/applications/{TEST_APP_ID}/parties")
        assert response.status_code == 404
