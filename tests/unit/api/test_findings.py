"""Unit tests for Finding API endpoints (list, verify, override, escalate)."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock  # noqa: TC003
from uuid import UUID, uuid4

from fastapi.testclient import TestClient  # noqa: TC002

from mil.kernel.errors import AuthorizationError, NotFoundError, ValidationError
from tests.unit.api.conftest import TEST_APP_ID, make_finding


@dataclass
class _FakeReviewSession:
    status: str
    escalated_to_role: str | None = None
    escalated_to_user_id: UUID | None = None


class TestListFindings:
    def test_returns_200(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        mock_finding_service.list_for_application.return_value = [make_finding()]
        mock_finding_review_actions.get_review_session.return_value = None
        mock_finding_review_actions.policy_version_for.return_value = "policy-pack-2026.2"
        response = client.get(f"/v1/applications/{TEST_APP_ID}/findings")
        assert response.status_code == 200

    def test_returns_all_explainability_and_attribution_fields(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        finding = make_finding()
        mock_finding_service.list_for_application.return_value = [finding]
        mock_finding_review_actions.get_review_session.return_value = None
        mock_finding_review_actions.policy_version_for.return_value = "policy-pack-2026.2"
        data = client.get(f"/v1/applications/{TEST_APP_ID}/findings").json()
        assert len(data) == 1
        item = data[0]
        for field in (
            "what",
            "why",
            "evidence_refs",
            "confidence",
            "recommended_action",
            "state",
            "model_version",
            "prompt_version",
            "extraction_version",
            "policy_version",
        ):
            assert field in item
        assert item["what"] == finding.title
        assert item["policy_version"] == "policy-pack-2026.2"

    def test_no_review_session_maps_to_unreviewed(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        mock_finding_service.list_for_application.return_value = [make_finding()]
        mock_finding_review_actions.get_review_session.return_value = None
        mock_finding_review_actions.policy_version_for.return_value = None
        data = client.get(f"/v1/applications/{TEST_APP_ID}/findings").json()
        assert data[0]["state"] == "unreviewed"

    def test_approved_session_maps_to_verified(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        mock_finding_service.list_for_application.return_value = [make_finding()]
        mock_finding_review_actions.get_review_session.return_value = _FakeReviewSession(
            status="APPROVED"
        )
        mock_finding_review_actions.policy_version_for.return_value = None
        data = client.get(f"/v1/applications/{TEST_APP_ID}/findings").json()
        assert data[0]["state"] == "verified"

    def test_overridden_session_maps_to_overridden(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        mock_finding_service.list_for_application.return_value = [make_finding()]
        mock_finding_review_actions.get_review_session.return_value = _FakeReviewSession(
            status="OVERRIDDEN"
        )
        mock_finding_review_actions.policy_version_for.return_value = None
        data = client.get(f"/v1/applications/{TEST_APP_ID}/findings").json()
        assert data[0]["state"] == "overridden"

    def test_escalated_session_maps_to_escalated_with_target_role(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        mock_finding_service.list_for_application.return_value = [make_finding()]
        mock_finding_review_actions.get_review_session.return_value = _FakeReviewSession(
            status="ESCALATED", escalated_to_role="COMPLIANCE_OFFICER"
        )
        mock_finding_review_actions.policy_version_for.return_value = None
        data = client.get(f"/v1/applications/{TEST_APP_ID}/findings").json()
        assert data[0]["state"] == "escalated"
        assert data[0]["escalated_to_role"] == "COMPLIANCE_OFFICER"

    def test_rejected_session_conservatively_maps_to_unreviewed(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        """See findings.py's `_finding_state` docstring for the rationale."""
        mock_finding_service.list_for_application.return_value = [make_finding()]
        mock_finding_review_actions.get_review_session.return_value = _FakeReviewSession(
            status="REJECTED"
        )
        mock_finding_review_actions.policy_version_for.return_value = None
        data = client.get(f"/v1/applications/{TEST_APP_ID}/findings").json()
        assert data[0]["state"] == "unreviewed"

    def test_authorization_error_returns_403(
        self, client: TestClient, mock_finding_service: MagicMock
    ) -> None:
        mock_finding_service.list_for_application.side_effect = AuthorizationError(
            "Permission denied: 'read:findings' is required"
        )
        response = client.get(f"/v1/applications/{TEST_APP_ID}/findings")
        assert response.status_code == 403


class TestVerifyFinding:
    def test_returns_200(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        finding = make_finding()
        mock_finding_service.get_by_id.return_value = finding
        mock_finding_review_actions.verify.return_value = _FakeReviewSession(status="APPROVED")
        mock_finding_review_actions.policy_version_for.return_value = None
        response = client.post(f"/v1/findings/{finding.id}/verify")
        assert response.status_code == 200

    def test_response_state_is_verified(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        finding = make_finding()
        mock_finding_service.get_by_id.return_value = finding
        mock_finding_review_actions.verify.return_value = _FakeReviewSession(status="APPROVED")
        mock_finding_review_actions.policy_version_for.return_value = None
        data = client.post(f"/v1/findings/{finding.id}/verify").json()
        assert data["state"] == "verified"

    def test_finding_not_found_returns_404(
        self, client: TestClient, mock_finding_service: MagicMock
    ) -> None:
        mock_finding_service.get_by_id.return_value = None
        response = client.post(f"/v1/findings/{uuid4()}/verify")
        assert response.status_code == 404

    def test_missing_review_session_returns_404(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        finding = make_finding()
        mock_finding_service.get_by_id.return_value = finding
        mock_finding_review_actions.verify.side_effect = NotFoundError("ReviewSession", finding.id)
        response = client.post(f"/v1/findings/{finding.id}/verify")
        assert response.status_code == 404

    def test_authorization_error_returns_403(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        """Covers both the base VERIFY_FINDING permission check and the
        escalation-ownership check — both raise AuthorizationError from
        FindingReviewActions.verify."""
        finding = make_finding()
        mock_finding_service.get_by_id.return_value = finding
        mock_finding_review_actions.verify.side_effect = AuthorizationError(
            "This finding was escalated to the COMPLIANCE_OFFICER role."
        )
        response = client.post(f"/v1/findings/{finding.id}/verify")
        assert response.status_code == 403


class TestOverrideFinding:
    def test_returns_200(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        finding = make_finding()
        mock_finding_service.get_by_id.return_value = finding
        mock_finding_review_actions.override.return_value = _FakeReviewSession(status="OVERRIDDEN")
        mock_finding_review_actions.policy_version_for.return_value = None
        response = client.post(
            f"/v1/findings/{finding.id}/override",
            json={
                "reason": "Income confirmed lower via payslip",
                "previous_value": "6500.00",
                "new_value": "6200.00",
            },
        )
        assert response.status_code == 200

    def test_response_state_is_overridden(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        finding = make_finding()
        mock_finding_service.get_by_id.return_value = finding
        mock_finding_review_actions.override.return_value = _FakeReviewSession(status="OVERRIDDEN")
        mock_finding_review_actions.policy_version_for.return_value = None
        data = client.post(
            f"/v1/findings/{finding.id}/override",
            json={
                "reason": "Income confirmed lower via payslip",
                "previous_value": "6500.00",
                "new_value": "6200.00",
            },
        ).json()
        assert data["state"] == "overridden"

    def test_empty_reason_returns_422(
        self, client: TestClient, mock_finding_service: MagicMock
    ) -> None:
        finding = make_finding()
        mock_finding_service.get_by_id.return_value = finding
        response = client.post(
            f"/v1/findings/{finding.id}/override",
            json={"reason": "", "previous_value": "6500.00", "new_value": "6200.00"},
        )
        assert response.status_code == 422

    def test_missing_new_value_returns_422(
        self, client: TestClient, mock_finding_service: MagicMock
    ) -> None:
        finding = make_finding()
        mock_finding_service.get_by_id.return_value = finding
        response = client.post(
            f"/v1/findings/{finding.id}/override",
            json={"reason": "A valid reason", "previous_value": "6500.00", "new_value": ""},
        )
        assert response.status_code == 422

    def test_service_validation_error_returns_422(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        finding = make_finding()
        mock_finding_service.get_by_id.return_value = finding
        mock_finding_review_actions.override.side_effect = ValidationError(
            "reason must not be empty", field="reason"
        )
        response = client.post(
            f"/v1/findings/{finding.id}/override",
            json={"reason": "A valid reason", "previous_value": "6500.00", "new_value": "6200.00"},
        )
        assert response.status_code == 422

    def test_finding_not_found_returns_404(
        self, client: TestClient, mock_finding_service: MagicMock
    ) -> None:
        mock_finding_service.get_by_id.return_value = None
        response = client.post(
            f"/v1/findings/{uuid4()}/override",
            json={"reason": "A valid reason", "previous_value": "6500.00", "new_value": "6200.00"},
        )
        assert response.status_code == 404

    def test_authorization_error_returns_403(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        finding = make_finding()
        mock_finding_service.get_by_id.return_value = finding
        mock_finding_review_actions.override.side_effect = AuthorizationError(
            "Permission denied: 'override:finding' is required"
        )
        response = client.post(
            f"/v1/findings/{finding.id}/override",
            json={"reason": "A valid reason", "previous_value": "6500.00", "new_value": "6200.00"},
        )
        assert response.status_code == 403


class TestEscalateFinding:
    def test_returns_200(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        finding = make_finding()
        mock_finding_service.get_by_id.return_value = finding
        mock_finding_review_actions.escalate.return_value = _FakeReviewSession(
            status="ESCALATED", escalated_to_role="COMPLIANCE_OFFICER"
        )
        mock_finding_review_actions.policy_version_for.return_value = None
        response = client.post(
            f"/v1/findings/{finding.id}/escalate",
            json={"reason": "Possible fair-lending concern", "target_role": "COMPLIANCE_OFFICER"},
        )
        assert response.status_code == 200

    def test_response_state_is_escalated_with_target_role(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        finding = make_finding()
        mock_finding_service.get_by_id.return_value = finding
        mock_finding_review_actions.escalate.return_value = _FakeReviewSession(
            status="ESCALATED", escalated_to_role="COMPLIANCE_OFFICER"
        )
        mock_finding_review_actions.policy_version_for.return_value = None
        data = client.post(
            f"/v1/findings/{finding.id}/escalate",
            json={"reason": "Possible fair-lending concern", "target_role": "COMPLIANCE_OFFICER"},
        ).json()
        assert data["state"] == "escalated"
        assert data["escalated_to_role"] == "COMPLIANCE_OFFICER"

    def test_empty_reason_returns_422(
        self, client: TestClient, mock_finding_service: MagicMock
    ) -> None:
        finding = make_finding()
        mock_finding_service.get_by_id.return_value = finding
        response = client.post(
            f"/v1/findings/{finding.id}/escalate",
            json={"reason": "", "target_role": "COMPLIANCE_OFFICER"},
        )
        assert response.status_code == 422

    def test_empty_target_role_returns_422(
        self, client: TestClient, mock_finding_service: MagicMock
    ) -> None:
        finding = make_finding()
        mock_finding_service.get_by_id.return_value = finding
        response = client.post(
            f"/v1/findings/{finding.id}/escalate",
            json={"reason": "A valid reason", "target_role": ""},
        )
        assert response.status_code == 422

    def test_service_validation_error_returns_422(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        finding = make_finding()
        mock_finding_service.get_by_id.return_value = finding
        mock_finding_review_actions.escalate.side_effect = ValidationError(
            "target_role must not be empty", field="target_role"
        )
        response = client.post(
            f"/v1/findings/{finding.id}/escalate",
            json={"reason": "A valid reason", "target_role": "COMPLIANCE_OFFICER"},
        )
        assert response.status_code == 422

    def test_finding_not_found_returns_404(
        self, client: TestClient, mock_finding_service: MagicMock
    ) -> None:
        mock_finding_service.get_by_id.return_value = None
        response = client.post(
            f"/v1/findings/{uuid4()}/escalate",
            json={"reason": "A valid reason", "target_role": "COMPLIANCE_OFFICER"},
        )
        assert response.status_code == 404

    def test_authorization_error_returns_403(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        finding = make_finding()
        mock_finding_service.get_by_id.return_value = finding
        mock_finding_review_actions.escalate.side_effect = AuthorizationError(
            "Permission denied: 'escalate:finding' is required"
        )
        response = client.post(
            f"/v1/findings/{finding.id}/escalate",
            json={"reason": "A valid reason", "target_role": "COMPLIANCE_OFFICER"},
        )
        assert response.status_code == 403

    def test_optional_target_user_id_accepted(
        self,
        client: TestClient,
        mock_finding_service: MagicMock,
        mock_finding_review_actions: MagicMock,
    ) -> None:
        finding = make_finding()
        target_user_id = uuid4()
        mock_finding_service.get_by_id.return_value = finding
        mock_finding_review_actions.escalate.return_value = _FakeReviewSession(
            status="ESCALATED",
            escalated_to_role="UNDERWRITER",
            escalated_to_user_id=target_user_id,
        )
        mock_finding_review_actions.policy_version_for.return_value = None
        response = client.post(
            f"/v1/findings/{finding.id}/escalate",
            json={
                "reason": "Please take a second look",
                "target_role": "UNDERWRITER",
                "target_user_id": str(target_user_id),
            },
        )
        assert response.status_code == 200
        assert response.json()["escalated_to_user_id"] == str(target_user_id)
