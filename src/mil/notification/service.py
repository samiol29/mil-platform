"""
NotificationService — use-case orchestrator for the Notification bounded
context (spec 005-enterprise-platform §13, Wave 2).

``notify()`` never constructs its own event description — it takes the id
of an ``AuditEvent`` the caller *already wrote* (via the shared
``AuditWriter``, in the same transaction as the action that produced it) and
creates a per-recipient pointer to it. This is the service-layer expression
of the spec's "integrate naturally with existing audit events, not a
duplicate model" instruction: there is no ``notify(event_type=..., data=
...)`` overload that would let a caller invent a description independent of
a real audit record.

Dependency rule: imports only from ``mil.notification``, ``mil.kernel``, and
the Python standard library. No other bounded context is imported — callers
(API routes) are responsible for having already written the audit event via
their own service (``PolicyService``, ``AssignmentService``, etc.).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mil.kernel.errors import NotFoundError
from mil.notification.models import Notification

if TYPE_CHECKING:
    from uuid import UUID

    from mil.kernel.security import AuthenticatedUser
    from mil.notification.repository import NotificationRepository


class NotificationService:
    def __init__(self, repository: NotificationRepository) -> None:
        self._repo = repository

    def notify(
        self, *, tenant_id: UUID, recipient_user_id: UUID, audit_event_id: UUID
    ) -> Notification:
        """Create a notification pointing at an already-written audit event."""
        notification = Notification.create(
            tenant_id=tenant_id,
            recipient_user_id=recipient_user_id,
            audit_event_id=audit_event_id,
        )
        self._repo.save(notification)
        return notification

    def list_for_caller(self, caller: AuthenticatedUser) -> list[Notification]:
        """A user only ever sees their own notifications — identity-scoped, not role-scoped."""
        return self._repo.get_for_recipient(caller.user_id)

    def unread_count(self, caller: AuthenticatedUser) -> int:
        return self._repo.get_unread_count(caller.user_id)

    def mark_read(self, caller: AuthenticatedUser, notification_id: UUID) -> Notification:
        notification = self._repo.get_by_id(notification_id)
        if notification is None or notification.recipient_user_id != caller.user_id:
            raise NotFoundError("Notification", notification_id)
        notification.mark_read()
        self._repo.save(notification)
        return notification
