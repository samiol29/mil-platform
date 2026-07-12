"""Unit tests for mil.notification.service — NotificationService."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from mil.kernel.errors import NotFoundError
from mil.kernel.security import AuthenticatedUser, Role
from mil.notification.service import NotificationService

if TYPE_CHECKING:
    from mil.notification.models import Notification


class FakeNotificationRepository:
    def __init__(self) -> None:
        self.notifications: dict[object, Notification] = {}

    def save(self, notification: Notification) -> None:
        self.notifications[notification.id] = notification

    def get_by_id(self, notification_id: object) -> Notification | None:
        return self.notifications.get(notification_id)

    def get_for_recipient(
        self, recipient_user_id: object, *, limit: int = 50
    ) -> list[Notification]:
        return [n for n in self.notifications.values() if n.recipient_user_id == recipient_user_id]

    def get_unread_count(self, recipient_user_id: object) -> int:
        return sum(
            1
            for n in self.notifications.values()
            if n.recipient_user_id == recipient_user_id and not n.is_read
        )


def _caller(tenant_id: object, user_id: object | None = None) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id or uuid4(), tenant_id=tenant_id, roles=frozenset({Role.UNDERWRITER})
    )


def _make_service() -> tuple[NotificationService, FakeNotificationRepository]:
    repo = FakeNotificationRepository()
    return NotificationService(repo), repo  # type: ignore[arg-type]


class TestNotify:
    def test_creates_notification_pointing_at_audit_event(self) -> None:
        service, _repo = _make_service()
        tenant_id, recipient, audit_event_id = uuid4(), uuid4(), uuid4()

        notification = service.notify(
            tenant_id=tenant_id, recipient_user_id=recipient, audit_event_id=audit_event_id
        )

        assert notification.audit_event_id == audit_event_id
        assert notification.recipient_user_id == recipient


class TestListForCaller:
    def test_only_returns_callers_own_notifications(self) -> None:
        service, _repo = _make_service()
        tenant_id = uuid4()
        recipient_id = uuid4()
        caller = _caller(tenant_id, recipient_id)

        service.notify(tenant_id=tenant_id, recipient_user_id=recipient_id, audit_event_id=uuid4())
        service.notify(tenant_id=tenant_id, recipient_user_id=uuid4(), audit_event_id=uuid4())

        notifications = service.list_for_caller(caller)
        assert len(notifications) == 1


class TestMarkRead:
    def test_marks_own_notification_read(self) -> None:
        service, _repo = _make_service()
        tenant_id, recipient = uuid4(), uuid4()
        caller = _caller(tenant_id, recipient)
        notification = service.notify(
            tenant_id=tenant_id, recipient_user_id=recipient, audit_event_id=uuid4()
        )

        marked = service.mark_read(caller, notification.id)

        assert marked.is_read is True

    def test_cannot_mark_someone_elses_notification_read(self) -> None:
        service, _repo = _make_service()
        tenant_id = uuid4()
        notification = service.notify(
            tenant_id=tenant_id, recipient_user_id=uuid4(), audit_event_id=uuid4()
        )
        other_caller = _caller(tenant_id)

        with pytest.raises(NotFoundError):
            service.mark_read(other_caller, notification.id)
