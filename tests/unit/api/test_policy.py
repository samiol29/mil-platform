"""Unit tests for Policy Engine + Policy Administration API endpoints (spec 005 §3/§4)."""

from __future__ import annotations

from unittest.mock import MagicMock  # noqa: TC003
from uuid import uuid4

from fastapi.testclient import TestClient  # noqa: TC002

from mil.kernel.errors import AuthorizationError, ConflictError, NotFoundError
from mil.policy.models import PolicyPack, PolicyPackApproval

TEST_TENANT_ID = uuid4()


def _make_pack(**overrides: object) -> PolicyPack:
    kwargs: dict[str, object] = {
        "tenant_id": TEST_TENANT_ID,
        "version": "1.0.0",
        "name": "Standard Pack",
        "content_hash": "a" * 8,
    }
    kwargs.update(overrides)
    return PolicyPack.create(**kwargs)  # type: ignore[arg-type]


class TestCreatePolicyPack:
    def test_returns_201(self, client: TestClient, mock_policy_service: MagicMock) -> None:
        mock_policy_service.create_pack.return_value = _make_pack()
        response = client.post(
            "/v1/policy-packs",
            json={"version": "1.0.0", "name": "Standard Pack", "content_hash": "a" * 8},
        )
        assert response.status_code == 201
        assert response.json()["is_active"] is False


class TestListPolicyPacks:
    def test_returns_200(self, client: TestClient, mock_policy_service: MagicMock) -> None:
        mock_policy_service.get_packs_for_tenant.return_value = [_make_pack()]
        response = client.get("/v1/policy-packs")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1


class TestSubmitForApproval:
    def test_returns_201(self, client: TestClient, mock_policy_service: MagicMock) -> None:
        pack = _make_pack()
        mock_policy_service.get_pack.return_value = pack
        mock_policy_service.submit_for_approval.return_value = PolicyPackApproval.create(
            policy_pack_id=pack.id, requested_by_user_id=uuid4()
        )
        response = client.post(f"/v1/policy-packs/{pack.id}/submit-for-approval")
        assert response.status_code == 201
        assert response.json()["decision"] == "PENDING"

    def test_duplicate_submission_returns_409(
        self, client: TestClient, mock_policy_service: MagicMock
    ) -> None:
        pack = _make_pack()
        mock_policy_service.get_pack.return_value = pack
        mock_policy_service.submit_for_approval.side_effect = ConflictError(
            "already has a pending approval request"
        )
        response = client.post(f"/v1/policy-packs/{pack.id}/submit-for-approval")
        assert response.status_code == 409


class TestApprovePolicyPack:
    def test_self_approval_returns_403(
        self, client: TestClient, mock_policy_service: MagicMock
    ) -> None:
        approval = PolicyPackApproval.create(policy_pack_id=uuid4(), requested_by_user_id=uuid4())
        mock_policy_service.get_approval.return_value = approval
        mock_policy_service.approve_pack.side_effect = AuthorizationError(
            "Permission denied: 'manage:policy_packs' is required"
        )
        response = client.post(f"/v1/policy-pack-approvals/{approval.id}/approve")
        assert response.status_code == 403

    def test_returns_200_on_success(
        self, client: TestClient, mock_policy_service: MagicMock
    ) -> None:
        approval = PolicyPackApproval.create(policy_pack_id=uuid4(), requested_by_user_id=uuid4())
        approval.approve(uuid4())
        mock_policy_service.get_approval.return_value = approval
        mock_policy_service.approve_pack.return_value = approval
        response = client.post(f"/v1/policy-pack-approvals/{approval.id}/approve")
        assert response.status_code == 200
        assert response.json()["decision"] == "APPROVED"


class TestActivatePolicyPack:
    def test_not_approved_returns_404(
        self, client: TestClient, mock_policy_service: MagicMock
    ) -> None:
        pack = _make_pack()
        mock_policy_service.get_pack.return_value = pack
        mock_policy_service.activate_pack_if_approved.side_effect = NotFoundError(
            "PolicyPackApproval", f"approved request for pack {pack.id}"
        )
        response = client.post(f"/v1/policy-packs/{pack.id}/activate")
        assert response.status_code == 404


class TestPolicyResults:
    def test_returns_200(self, client: TestClient, mock_policy_service: MagicMock) -> None:
        mock_policy_service.get_results_for_application.return_value = []
        response = client.get(f"/v1/applications/{uuid4()}/policy-results")
        assert response.status_code == 200
        assert response.json()["items"] == []
