"""
Document Checklist REST endpoints — internal-staff-facing, MIL API v1
(spec 005-enterprise-platform §12, Wave 4 — Customer Portal).

Endpoints:
    POST /v1/applications/{application_id}/checklist-items                     Request a document
    GET  /v1/applications/{application_id}/checklist-items                     List checklist items
    POST /v1/applications/{application_id}/checklist-items/{item_id}/waive     Waive a request
    POST /v1/applications/{application_id}/checklist-items/{item_id}/invite-borrower
                                                                                 Invite a borrower

Route handlers are thin; `PortalWorkspace`'s methods delegate to
`PortalService`, which self-checks `manage:checklist`/`read:application`.

Dependency rule: imports from `mil.api.deps`, `mil.api.v1.schemas`, FastAPI,
and the Python standard library only.
"""

from __future__ import annotations

from uuid import UUID  # noqa: TC003

from fastapi import APIRouter

from mil.api.deps import CurrentUser, PortalWorkspaceDep  # noqa: TC001
from mil.api.v1.schemas import (
    ChecklistItemListResponse,
    ChecklistItemResponse,
    CreateChecklistItemRequest,
    InviteBorrowerRequest,
    InviteBorrowerResponse,
)

router = APIRouter(prefix="/v1/applications/{application_id}", tags=["Customer Portal (internal)"])


def _item_response(item: object) -> ChecklistItemResponse:
    return ChecklistItemResponse(
        id=item.id,  # type: ignore[attr-defined]
        application_id=item.application_id,  # type: ignore[attr-defined]
        party_id=item.party_id,  # type: ignore[attr-defined]
        label=item.label,  # type: ignore[attr-defined]
        document_type=item.document_type,  # type: ignore[attr-defined]
        status=item.status,  # type: ignore[attr-defined]
        requested_by_user_id=item.requested_by_user_id,  # type: ignore[attr-defined]
        fulfilled_document_id=item.fulfilled_document_id,  # type: ignore[attr-defined]
        requested_at=item.requested_at,  # type: ignore[attr-defined]
    )


@router.post(
    "/checklist-items",
    summary="Request a document from a borrower",
    response_model=ChecklistItemResponse,
    responses={403: {"description": "Insufficient permissions"}},
)
def create_checklist_item(
    application_id: UUID,
    body: CreateChecklistItemRequest,
    user: CurrentUser,
    workspace: PortalWorkspaceDep,
) -> ChecklistItemResponse:
    item = workspace.create_checklist_item(
        user,
        application_id=application_id,
        label=body.label,
        document_type=body.document_type,
        party_id=body.party_id,
    )
    return _item_response(item)


@router.get(
    "/checklist-items",
    summary="List an application's document checklist",
    response_model=ChecklistItemListResponse,
)
def list_checklist_items(
    application_id: UUID, user: CurrentUser, workspace: PortalWorkspaceDep
) -> ChecklistItemListResponse:
    items = workspace.get_checklist_for_application(user, application_id)
    return ChecklistItemListResponse(items=[_item_response(i) for i in items])


@router.post(
    "/checklist-items/{item_id}/waive",
    summary="Waive a checklist item — no longer required",
    response_model=ChecklistItemResponse,
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Item not found"},
    },
)
def waive_checklist_item(
    application_id: UUID,
    item_id: UUID,
    user: CurrentUser,
    workspace: PortalWorkspaceDep,
) -> ChecklistItemResponse:
    item = workspace.waive_item(user, item_id)
    return _item_response(item)


@router.post(
    "/checklist-items/{item_id}/invite-borrower",
    summary="Invite a borrower to the Customer Portal",
    response_model=InviteBorrowerResponse,
    responses={403: {"description": "Insufficient permissions"}},
)
def invite_borrower(
    application_id: UUID,
    item_id: UUID,
    body: InviteBorrowerRequest,
    user: CurrentUser,
    workspace: PortalWorkspaceDep,
) -> InviteBorrowerResponse:
    account, raw_token = workspace.invite_borrower(user, party_id=body.party_id, email=body.email)
    return InviteBorrowerResponse(
        portal_account_id=account.id, status=account.status, activation_token=raw_token
    )
