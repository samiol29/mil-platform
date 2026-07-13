"""
Customer Portal REST endpoints — borrower-facing, MIL API v1 (spec 005-
enterprise-platform §12, Wave 4).

Endpoints:
    POST /v1/portal/auth/activate         Activate a portal account, get a session token
    GET  /v1/portal/checklist             This borrower's own document checklist
    POST /v1/portal/checklist/{id}/upload Fulfill a checklist item by uploading a document
    GET  /v1/portal/status                A plain-language application status

A genuinely separate auth realm from the internal API: every route here
depends on ``CurrentPortalClaims`` (a verified ``PortalSessionClaims``),
never ``CurrentUser`` — a portal session token cannot be used against any
internal endpoint, and vice versa (see ``mil.api.deps``'s own module
docstring for the verification mechanism). Never exposes AI reasoning,
Findings, Evidence, Policy results, internal comments, or Timeline/Audit
detail — only a borrower-safe status label and the document checklist.

Dependency rule: imports from `mil.api.deps`, `mil.api.v1.schemas`, FastAPI,
and the Python standard library only.
"""

from __future__ import annotations

from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, Form, UploadFile

from mil.api.deps import CurrentPortalClaims, PortalWorkspaceDep, SettingsDep  # noqa: TC001
from mil.api.v1.documents import _read_upload_within_limit
from mil.api.v1.schemas import (
    PORTAL_STATUS_LABELS,
    ChecklistItemListResponse,
    ChecklistItemResponse,
    PortalActivateRequest,
    PortalSessionResponse,
    PortalStatusResponse,
)

router = APIRouter(prefix="/v1/portal", tags=["Customer Portal"])


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
    "/auth/activate",
    summary="Activate a Customer Portal account and receive a session token",
    response_model=PortalSessionResponse,
    responses={401: {"description": "Invalid or expired activation token"}},
)
def activate(
    body: PortalActivateRequest, workspace: PortalWorkspaceDep, settings: SettingsDep
) -> PortalSessionResponse:
    secret = settings.mil_portal_secret_key.get_secret_value().encode("utf-8")
    session_token = workspace.activate_account(
        party_id=body.party_id, raw_token=body.token, secret=secret
    )
    return PortalSessionResponse(session_token=session_token)


@router.get(
    "/checklist",
    summary="This borrower's own document checklist",
    response_model=ChecklistItemListResponse,
)
def get_checklist(
    claims: CurrentPortalClaims, workspace: PortalWorkspaceDep
) -> ChecklistItemListResponse:
    items = workspace.get_checklist_for_claims(claims)
    return ChecklistItemListResponse(items=[_item_response(i) for i in items])


@router.get(
    "/status",
    summary="This borrower's application status, in plain language",
    response_model=PortalStatusResponse,
)
def get_status(claims: CurrentPortalClaims, workspace: PortalWorkspaceDep) -> PortalStatusResponse:
    application = workspace.get_status_for_claims(claims)
    label = PORTAL_STATUS_LABELS.get(application.status, "In progress")
    return PortalStatusResponse(status_label=label)


@router.post(
    "/checklist/{item_id}/upload",
    summary="Upload a document to fulfill a checklist item",
    response_model=ChecklistItemResponse,
    responses={
        404: {"description": "Checklist item not found"},
        413: {"description": "File too large"},
    },
)
async def upload_for_checklist_item(
    item_id: UUID,
    claims: CurrentPortalClaims,
    workspace: PortalWorkspaceDep,
    settings: SettingsDep,
    file: UploadFile,
    document_type: str = Form(...),
) -> ChecklistItemResponse:
    content = await _read_upload_within_limit(file, settings.mil_max_upload_bytes)
    original_filename = file.filename or "unknown"
    item = workspace.upload_for_claims(
        claims,
        item_id=item_id,
        content=content,
        original_filename=original_filename,
        document_type=document_type,
    )
    return _item_response(item)
