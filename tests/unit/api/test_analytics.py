"""Unit tests for Business Analytics API endpoints (spec 005 §11, Wave 3)."""

from __future__ import annotations

from unittest.mock import MagicMock  # noqa: TC003

from fastapi.testclient import TestClient  # noqa: TC002

from mil.api.deps import BusinessAnalyticsSnapshot, FindingOutcomeRow, PolicyOutcomeRow
from mil.kernel.errors import AuthorizationError


class TestGetSnapshot:
    def test_returns_200(
        self, client: TestClient, mock_business_analytics_workspace: MagicMock
    ) -> None:
        snapshot = BusinessAnalyticsSnapshot(
            application_counts_by_status=(("DRAFT", 2), ("UNDER_REVIEW", 1)),
            finding_outcomes=(FindingOutcomeRow(lifecycle_state="verified", count=3),),
            policy_outcomes=(PolicyOutcomeRow(policy_version="1.0.0", outcome="FLAGGED", count=2),),
            document_count=10,
            evidence_count=25,
            average_review_duration_seconds=1800.0,
        )
        mock_business_analytics_workspace.get_snapshot.return_value = snapshot
        response = client.get("/v1/analytics/snapshot")
        assert response.status_code == 200
        body = response.json()
        assert body["document_count"] == 10
        assert body["evidence_count"] == 25
        assert body["average_review_duration_seconds"] == 1800.0
        assert body["application_counts_by_status"] == [
            {"status": "DRAFT", "count": 2},
            {"status": "UNDER_REVIEW", "count": 1},
        ]
        assert body["finding_outcomes"] == [{"lifecycle_state": "verified", "count": 3}]
        assert body["policy_outcomes"] == [
            {"policy_version": "1.0.0", "outcome": "FLAGGED", "count": 2}
        ]

    def test_returns_null_average_review_duration_when_no_closed_sessions(
        self, client: TestClient, mock_business_analytics_workspace: MagicMock
    ) -> None:
        snapshot = BusinessAnalyticsSnapshot(
            application_counts_by_status=(),
            finding_outcomes=(),
            policy_outcomes=(),
            document_count=0,
            evidence_count=0,
            average_review_duration_seconds=None,
        )
        mock_business_analytics_workspace.get_snapshot.return_value = snapshot
        response = client.get("/v1/analytics/snapshot")
        assert response.status_code == 200
        assert response.json()["average_review_duration_seconds"] is None

    def test_readonly_role_returns_403(
        self, client: TestClient, mock_business_analytics_workspace: MagicMock
    ) -> None:
        mock_business_analytics_workspace.get_snapshot.side_effect = AuthorizationError(
            "Permission denied: 'read:analytics' is required"
        )
        response = client.get("/v1/analytics/snapshot")
        assert response.status_code == 403
