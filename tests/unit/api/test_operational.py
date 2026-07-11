"""Unit tests for Operational Dashboard API endpoints (spec 005 §10, Wave 3)."""

from __future__ import annotations

from unittest.mock import MagicMock  # noqa: TC003

from fastapi.testclient import TestClient  # noqa: TC002

from mil.api.deps import ApplicationFunnelRow, QueueDepthRow
from mil.kernel.errors import AuthorizationError


class TestGetQueueDepth:
    def test_returns_200(
        self, client: TestClient, mock_operational_workspace: MagicMock
    ) -> None:
        mock_operational_workspace.get_queue_depth.return_value = [
            QueueDepthRow(workflow_type="DOCUMENT_INGESTION", status="PENDING", count=3)
        ]
        response = client.get("/v1/operational/queue-depth")
        assert response.status_code == 200
        assert response.json()["items"] == [
            {"workflow_type": "DOCUMENT_INGESTION", "status": "PENDING", "count": 3}
        ]

    def test_readonly_role_returns_403(
        self, client: TestClient, mock_operational_workspace: MagicMock
    ) -> None:
        mock_operational_workspace.get_queue_depth.side_effect = AuthorizationError(
            "Permission denied: 'read:operational' is required"
        )
        response = client.get("/v1/operational/queue-depth")
        assert response.status_code == 403


class TestGetPoisonJobs:
    def test_returns_200(
        self, client: TestClient, mock_operational_workspace: MagicMock
    ) -> None:
        from datetime import UTC, datetime
        from uuid import uuid4

        step = MagicMock()
        step.id = uuid4()
        step.workflow_run_id = uuid4()
        step.step_name = "OCR"
        step.status = "FAILED"
        step.retry_count = 3
        step.max_retries = 3
        step.error_code = "PROVIDER_TIMEOUT"
        step.error_message = "Timed out"
        step.updated_at = datetime.now(UTC)
        mock_operational_workspace.get_poison_jobs.return_value = [step]
        response = client.get("/v1/operational/poison-jobs")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1
        assert response.json()["items"][0]["step_name"] == "OCR"


class TestGetFunnel:
    def test_returns_200(
        self, client: TestClient, mock_operational_workspace: MagicMock
    ) -> None:
        mock_operational_workspace.get_funnel.return_value = [
            ApplicationFunnelRow(status="DRAFT", count=2, avg_seconds_since_updated=3600.0)
        ]
        response = client.get("/v1/operational/funnel")
        assert response.status_code == 200
        assert response.json()["items"] == [
            {"status": "DRAFT", "count": 2, "avg_seconds_since_updated": 3600.0}
        ]


class TestGetJobQueueHealth:
    def test_returns_200(
        self, client: TestClient, mock_operational_workspace: MagicMock
    ) -> None:
        from mil.api.deps import JobQueueHealth

        mock_operational_workspace.get_job_queue_health.return_value = JobQueueHealth(
            pending_count=3, processing_count=1, dead_letter_count=0
        )
        response = client.get("/v1/operational/job-queue-health")
        assert response.status_code == 200
        assert response.json() == {"pending_count": 3, "processing_count": 1, "dead_letter_count": 0}
