"""Persistence gateway for the Notification bounded context."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from mil.notification.models import Notification

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session


class NotificationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, notification: Notification) -> None:
        self._session.add(notification)
        self._session.flush()

    def get_by_id(self, notification_id: UUID) -> Notification | None:
        return self._session.get(Notification, notification_id)

    def get_for_recipient(self, recipient_user_id: UUID, *, limit: int = 50) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.recipient_user_id == recipient_user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt))

    def get_unread_count(self, recipient_user_id: UUID) -> int:
        stmt = select(func.count()).where(
            Notification.recipient_user_id == recipient_user_id,
            Notification.read_at.is_(None),
        )
        return self._session.scalar(stmt) or 0
