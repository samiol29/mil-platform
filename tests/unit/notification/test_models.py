"""Unit tests for mil.notification.models — Notification."""

from __future__ import annotations

from uuid import uuid4

from mil.notification.models import Notification


class TestNotification:
    def test_create_is_unread(self) -> None:
        notification = Notification.create(
            tenant_id=uuid4(), recipient_user_id=uuid4(), audit_event_id=uuid4()
        )
        assert notification.is_read is False
        assert notification.read_at is None

    def test_mark_read(self) -> None:
        notification = Notification.create(
            tenant_id=uuid4(), recipient_user_id=uuid4(), audit_event_id=uuid4()
        )
        notification.mark_read()
        assert notification.is_read is True

    def test_mark_read_is_idempotent(self) -> None:
        notification = Notification.create(
            tenant_id=uuid4(), recipient_user_id=uuid4(), audit_event_id=uuid4()
        )
        notification.mark_read()
        first = notification.read_at
        notification.mark_read()
        assert notification.read_at == first
