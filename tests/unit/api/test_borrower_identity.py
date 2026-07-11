"""Unit tests for Borrower Identity Resolution API endpoints (spec 005 §5, Wave 3)."""

from __future__ import annotations

from unittest.mock import MagicMock  # noqa: TC003
from uuid import uuid4

from fastapi.testclient import TestClient  # noqa: TC002

from mil.borrower_identity.models import BorrowerIdentity, BorrowerIdentityMember, IdentityMatchCandidate
from mil.cross_application_intelligence.service import CrossApplicationObservation
from mil.kernel.errors import AuthorizationError, NotFoundError


def _make_candidate(**overrides: object) -> IdentityMatchCandidate:
    candidate = IdentityMatchCandidate.create(
        tenant_id=overrides.get("tenant_id", uuid4()),
        party_id=overrides.get("party_id", uuid4()),
        candidate_party_id=overrides.get("candidate_party_id", uuid4()),
        match_score=overrides.get("match_score", 0.98),
        match_basis=overrides.get("match_basis", {"exact_identifier_match": True}),
    )
    return candidate


class TestComputeMatchCandidates:
    def test_returns_200(
        self, client: TestClient, mock_borrower_identity_workspace: MagicMock
    ) -> None:
        candidate = _make_candidate()
        mock_borrower_identity_workspace.compute_candidates.return_value = [candidate]
        response = client.post(f"/v1/parties/{uuid4()}/compute-match-candidates")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1
        assert response.json()["items"][0]["match_score"] == 0.98

    def test_party_not_found_returns_404(
        self, client: TestClient, mock_borrower_identity_workspace: MagicMock
    ) -> None:
        mock_borrower_identity_workspace.compute_candidates.side_effect = NotFoundError(
            "Party", uuid4()
        )
        response = client.post(f"/v1/parties/{uuid4()}/compute-match-candidates")
        assert response.status_code == 404

    def test_readonly_role_returns_403(
        self, client: TestClient, mock_borrower_identity_workspace: MagicMock
    ) -> None:
        mock_borrower_identity_workspace.compute_candidates.side_effect = AuthorizationError(
            "Permission denied: 'confirm:identity_match' is required"
        )
        response = client.post(f"/v1/parties/{uuid4()}/compute-match-candidates")
        assert response.status_code == 403


class TestListMatchCandidates:
    def test_returns_200(
        self, client: TestClient, mock_borrower_identity_workspace: MagicMock
    ) -> None:
        mock_borrower_identity_workspace.get_candidates_for_party.return_value = [_make_candidate()]
        response = client.get(f"/v1/parties/{uuid4()}/match-candidates")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1


class TestGetIdentityForParty:
    def test_returns_null_when_none_exists(
        self, client: TestClient, mock_borrower_identity_workspace: MagicMock
    ) -> None:
        mock_borrower_identity_workspace.get_identity_for_party.return_value = None
        response = client.get(f"/v1/parties/{uuid4()}/borrower-identity")
        assert response.status_code == 200
        assert response.json() is None

    def test_returns_identity_when_exists(
        self, client: TestClient, mock_borrower_identity_workspace: MagicMock
    ) -> None:
        identity = BorrowerIdentity.create(tenant_id=uuid4(), primary_display_name="Jane Smith")
        mock_borrower_identity_workspace.get_identity_for_party.return_value = identity
        response = client.get(f"/v1/parties/{uuid4()}/borrower-identity")
        assert response.status_code == 200
        assert response.json()["primary_display_name"] == "Jane Smith"


class TestConfirmMatch:
    def test_returns_200(
        self, client: TestClient, mock_borrower_identity_workspace: MagicMock
    ) -> None:
        identity = BorrowerIdentity.create(tenant_id=uuid4(), primary_display_name="")
        mock_borrower_identity_workspace.confirm_match.return_value = identity
        response = client.post(f"/v1/match-candidates/{uuid4()}/confirm")
        assert response.status_code == 200
        assert response.json()["id"] == str(identity.id)

    def test_candidate_not_found_returns_404(
        self, client: TestClient, mock_borrower_identity_workspace: MagicMock
    ) -> None:
        mock_borrower_identity_workspace.confirm_match.side_effect = NotFoundError(
            "IdentityMatchCandidate", uuid4()
        )
        response = client.post(f"/v1/match-candidates/{uuid4()}/confirm")
        assert response.status_code == 404


class TestRejectMatch:
    def test_returns_200(
        self, client: TestClient, mock_borrower_identity_workspace: MagicMock
    ) -> None:
        candidate = _make_candidate()
        candidate.reject(uuid4(), reason="Not the same borrower")
        mock_borrower_identity_workspace.reject_match.return_value = candidate
        response = client.post(
            f"/v1/match-candidates/{uuid4()}/reject", json={"reason": "Not the same borrower"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "REJECTED"
        assert response.json()["reason"] == "Not the same borrower"


class TestGetIdentity:
    def test_returns_200(
        self, client: TestClient, mock_borrower_identity_workspace: MagicMock
    ) -> None:
        identity = BorrowerIdentity.create(tenant_id=uuid4(), primary_display_name="Jane Smith")
        mock_borrower_identity_workspace.get_identity.return_value = identity
        response = client.get(f"/v1/borrower-identities/{identity.id}")
        assert response.status_code == 200
        assert response.json()["primary_display_name"] == "Jane Smith"

    def test_not_found_returns_404(
        self, client: TestClient, mock_borrower_identity_workspace: MagicMock
    ) -> None:
        mock_borrower_identity_workspace.get_identity.side_effect = NotFoundError(
            "BorrowerIdentity", uuid4()
        )
        response = client.get(f"/v1/borrower-identities/{uuid4()}")
        assert response.status_code == 404


class TestGetIdentityMembers:
    def test_returns_200(
        self, client: TestClient, mock_borrower_identity_workspace: MagicMock
    ) -> None:
        member = BorrowerIdentityMember.create(
            borrower_identity_id=uuid4(),
            party_id=uuid4(),
            application_id=uuid4(),
            linked_by_user_id=uuid4(),
        )
        mock_borrower_identity_workspace.get_members.return_value = [member]
        response = client.get(f"/v1/borrower-identities/{uuid4()}/members")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1


class TestGetCrossApplicationSignals:
    def test_returns_200(
        self, client: TestClient, mock_cross_application_intelligence_workspace: MagicMock
    ) -> None:
        observation = CrossApplicationObservation(
            kind="REUSED_DOCUMENT",
            description="Same document reused across 2 applications.",
            application_ids=(uuid4(), uuid4()),
            document_ids=(uuid4(), uuid4()),
        )
        mock_cross_application_intelligence_workspace.get_signals.return_value = [observation]
        response = client.get(f"/v1/borrower-identities/{uuid4()}/cross-application-signals")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1
        assert response.json()["items"][0]["kind"] == "REUSED_DOCUMENT"

    def test_not_found_returns_404(
        self, client: TestClient, mock_cross_application_intelligence_workspace: MagicMock
    ) -> None:
        mock_cross_application_intelligence_workspace.get_signals.side_effect = NotFoundError(
            "BorrowerIdentity", uuid4()
        )
        response = client.get(f"/v1/borrower-identities/{uuid4()}/cross-application-signals")
        assert response.status_code == 404

    def test_readonly_role_returns_403(
        self, client: TestClient, mock_cross_application_intelligence_workspace: MagicMock
    ) -> None:
        mock_cross_application_intelligence_workspace.get_signals.side_effect = AuthorizationError(
            "Permission denied: 'read:cross_application_identity' is required"
        )
        response = client.get(f"/v1/borrower-identities/{uuid4()}/cross-application-signals")
        assert response.status_code == 403
