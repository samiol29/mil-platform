"""
LOS Integration REST endpoints — MIL API v1 (spec 005-enterprise-platform
§2, Wave 2).

Endpoints:
    POST   /v1/integrations/los/connections                     Register a connection (admin)
    GET    /v1/integrations/los/connections                      List connections (admin)
    GET    /v1/integrations/los/sync-events?outcome=FAILURE       Sync Failure Queue (admin)
    POST   /v1/applications/{application_id}/los-sync             Pull from the LOS (inbound)
    POST   /v1/applications/{application_id}/los-push             Push readiness (outbound)
    GET    /v1/applications/{application_id}/los-sync-events       Sync history for an application

Route handlers are thin. `IntegrationService`'s methods self-check
`manage:integration`/`push:los_status`. `IntegrationWorkspace` (mil.api.deps)
resolves the application's real `los_reference` and the registered
`LOSAdapter` from the DI container — this route module never imports either
`mil.application` or the adapter interface directly.

Dependency rule: imports from `mil.api.deps`, `mil.api.v1.schemas`, FastAPI,
and the Python standard library only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, Query, status

from mil.api.deps import CurrentUser, IntegrationWorkspaceDep  # noqa: TC001
from mil.api.v1.schemas import (
    CreateLOSConnectionRequest,
    LOSConnectionListResponse,
    LOSConnectionResponse,
    LOSSyncEventListResponse,
    LOSSyncEventResponse,
    PushReadinessRequest,
)

if TYPE_CHECKING:
    from mil.integration.models import LOSConnection, LOSSyncEvent

router = APIRouter(prefix="/v1/integrations/los", tags=["Integration"])
application_integration_router = APIRouter(
    prefix="/v1/applications/{application_id}", tags=["Integration"]
)


def _connection_response(connection: LOSConnection) -> LOSConnectionResponse:
    return LOSConnectionResponse(
        id=connection.id,
        tenant_id=connection.tenant_id,
        vendor_type=connection.vendor_type,
        status=connection.status,
        created_by_user_id=connection.created_by_user_id,
        created_at=connection.created_at,
    )


def _sync_event_response(event: LOSSyncEvent) -> LOSSyncEventResponse:
    return LOSSyncEventResponse(
        id=event.id,
        application_id=event.application_id,
        direction=event.direction,
        outcome=event.outcome,
        detail=event.detail,
        error_message=event.error_message,
        initiated_by_user_id=event.initiated_by_user_id,
        occurred_at=event.occurred_at,
    )


@router.post(
    "/connections",
    summary="Register a LOS connection",
    response_model=LOSConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_connection(
    body: CreateLOSConnectionRequest, user: CurrentUser, workspace: IntegrationWorkspaceDep
) -> LOSConnectionResponse:
    connection = workspace.service.create_connection(user, vendor_type=body.vendor_type)
    return _connection_response(connection)


@router.get(
    "/connections", summary="List LOS connections", response_model=LOSConnectionListResponse
)
def list_connections(
    user: CurrentUser, workspace: IntegrationWorkspaceDep
) -> LOSConnectionListResponse:
    connections = workspace.service.list_connections(user)
    return LOSConnectionListResponse(items=[_connection_response(c) for c in connections])


@router.get(
    "/sync-events",
    summary="The Sync Failure Queue (or all sync events) for the tenant",
    response_model=LOSSyncEventListResponse,
)
def list_failed_sync_events(
    user: CurrentUser,
    workspace: IntegrationWorkspaceDep,
    outcome: str | None = Query(default="FAILURE"),
) -> LOSSyncEventListResponse:
    events = workspace.service.get_failed_sync_events(user) if outcome == "FAILURE" else []
    return LOSSyncEventListResponse(items=[_sync_event_response(e) for e in events])


@application_integration_router.post(
    "/los-sync",
    summary="Pull the application's current state from the LOS",
    response_model=LOSSyncEventResponse,
    responses={
        404: {"description": "Application not found"},
        422: {"description": "Application has no los_reference set"},
    },
)
def sync_application(
    application_id: UUID, user: CurrentUser, workspace: IntegrationWorkspaceDep
) -> LOSSyncEventResponse:
    event = workspace.sync_application(user, application_id)
    return _sync_event_response(event)


@application_integration_router.post(
    "/los-push",
    summary="Push a Mortgage Readiness assessment to the LOS",
    response_model=LOSSyncEventResponse,
)
def push_readiness(
    application_id: UUID,
    body: PushReadinessRequest,
    user: CurrentUser,
    workspace: IntegrationWorkspaceDep,
) -> LOSSyncEventResponse:
    event = workspace.push_readiness(
        user,
        application_id,
        is_ready=body.is_ready,
        summary=body.summary,
        missing_items=tuple(body.missing_items),
    )
    return _sync_event_response(event)


@application_integration_router.get(
    "/los-sync-events",
    summary="List LOS sync/push history for an application",
    response_model=LOSSyncEventListResponse,
)
def list_application_sync_events(
    application_id: UUID, user: CurrentUser, workspace: IntegrationWorkspaceDep
) -> LOSSyncEventListResponse:
    events = workspace.service.get_sync_events(user, application_id)
    return LOSSyncEventListResponse(items=[_sync_event_response(e) for e in events])
