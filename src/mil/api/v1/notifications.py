"""
Notification REST endpoints — MIL API v1 (spec 005-enterprise-platform §13,
Wave 2).

Endpoints:
    GET  /v1/notifications              List the caller's own notifications
    POST /v1/notifications/{id}/read     Mark one notification read

Every notification's display fields (``event_type``/``event_data``/
``occurred_at``) are resolved live from the ``AuditEvent`` it points at
(`NotificationWorkspace`) — never stored redundantly, per the model's own
"no duplicate event model" discipline.

Dependency rule: imports from `mil.api.deps`, `mil.api.v1.schemas`, FastAPI,
and the Python standard library only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from fastapi import APIRouter

from mil.api.deps import CurrentUser, NotificationWorkspaceDep  # noqa: TC001
from mil.api.v1.schemas import NotificationListResponse, NotificationResponse

if TYPE_CHECKING:
    from mil.audit.models import AuditEvent
    from mil.notification.models import Notification

router = APIRouter(prefix="/v1/notifications", tags=["Notifications"])


def _notification_response(
    notification: Notification, event: AuditEvent | None
) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        recipient_user_id=notification.recipient_user_id,
        audit_event_id=notification.audit_event_id,
        event_type=event.event_type if event is not None else "UNKNOWN",
        event_data=event.event_data if event is not None else {},
        occurred_at=event.occurred_at if event is not None else notification.created_at,
        read_at=notification.read_at,
        created_at=notification.created_at,
    )


@router.get("", summary="List the caller's own notifications", response_model=NotificationListResponse)
def list_notifications(
    user: CurrentUser, workspace: NotificationWorkspaceDep
) -> NotificationListResponse:
    items = workspace.list_for_caller(user)
    return NotificationListResponse(
        items=[_notification_response(n, e) for n, e in items],
        unread_count=workspace.unread_count(user),
    )


@router.post(
    "/{notification_id}/read",
    summary="Mark a notification as read",
    response_model=NotificationResponse,
    responses={404: {"description": "Notification not found, or not the caller's own"}},
)
def mark_read(
    notification_id: UUID, user: CurrentUser, workspace: NotificationWorkspaceDep
) -> NotificationResponse:
    notification, event = workspace.mark_read(user, notification_id)
    return _notification_response(notification, event)
