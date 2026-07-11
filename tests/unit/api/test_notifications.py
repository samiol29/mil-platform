"""Unit tests for Notification API endpoints (spec 005 §13, Wave 2)."""

from __future__ import annotations

from unittest.mock import MagicMock  # noqa: TC003
from uuid import uuid4

from fastapi.testclient import TestClient  # noqa: TC002

from mil.kernel.errors import NotFoundError
from mil.notification.models import Notification


class TestListNotifications:
    def test_returns_notifications_with_resolved_event_fields(
        self, client: TestClient, mock_notification_workspace: MagicMock
    ) -> None:
        notification = Notification.create(
            tenant_id=uuid4(), recipient_user_id=uuid4(), audit_event_id=uuid4()
        )

        class FakeEvent:
            event_type = "REVIEW_COMMENT_ADDED"
            event_data = {"comment_id": "abc"}
            occurred_at = notification.created_at

        mock_notification_workspace.list_for_caller.return_value = [(notification, FakeEvent())]
        mock_notification_workspace.unread_count.return_value = 1

        response = client.get("/v1/notifications")

        assert response.status_code == 200
        body = response.json()
        assert body["unread_count"] == 1
        assert body["items"][0]["event_type"] == "REVIEW_COMMENT_ADDED"

    def test_missing_audit_event_falls_back_honestly(
        self, client: TestClient, mock_notification_workspace: MagicMock
    ) -> None:
        notification = Notification.create(
            tenant_id=uuid4(), recipient_user_id=uuid4(), audit_event_id=uuid4()
        )
        mock_notification_workspace.list_for_caller.return_value = [(notification, None)]
        mock_notification_workspace.unread_count.return_value = 0

        response = client.get("/v1/notifications")

        assert response.status_code == 200
        assert response.json()["items"][0]["event_type"] == "UNKNOWN"


class TestMarkRead:
    def test_returns_200(self, client: TestClient, mock_notification_workspace: MagicMock) -> None:
        notification = Notification.create(
            tenant_id=uuid4(), recipient_user_id=uuid4(), audit_event_id=uuid4()
        )
        notification.mark_read()
        mock_notification_workspace.mark_read.return_value = (notification, None)

        response = client.post(f"/v1/notifications/{uuid4()}/read")

        assert response.status_code == 200
        assert response.json()["read_at"] is not None

    def test_not_found_returns_404(
        self, client: TestClient, mock_notification_workspace: MagicMock
    ) -> None:
        mock_notification_workspace.mark_read.side_effect = NotFoundError("Notification", uuid4())
        response = client.post(f"/v1/notifications/{uuid4()}/read")
        assert response.status_code == 404
