"""
Universal Search REST endpoint — MIL API v1 (spec 005-enterprise-platform
§7, Wave 2).

    GET /v1/search?q=&kinds=application,document

One query, typed results across every supported entity — built on the
existing `Application.search`/new `Document.search_for_tenant` repository
methods (`SearchWorkspace`, `mil.api.deps`), not a new search engine or
index. Deliberately modular: `kinds` lets a caller narrow to one entity type
(matching what the Command Palette needs) without duplicating the endpoint.

Every result kind enforces the same permission its own resource's list
endpoint already requires (`READ_APPLICATION`/`READ_DOCUMENT`) — search is
never a side channel around RBAC.

Dependency rule: imports from `mil.api.deps`, `mil.api.v1.schemas`, FastAPI,
and the Python standard library only.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from mil.api.deps import CurrentUser, SearchWorkspaceDep  # noqa: TC001
from mil.api.v1.schemas import (
    ApplicationResponse,
    ApplicationSearchResult,
    DocumentSearchResult,
    SearchResponse,
)
from mil.kernel.security import Permission, require_permission

router = APIRouter(prefix="/v1/search", tags=["Search"])

_DEFAULT_KINDS = ("application", "document")


@router.get("", summary="Search across applications and documents", response_model=SearchResponse)
def search(
    user: CurrentUser,
    workspace: SearchWorkspaceDep,
    q: str = Query(min_length=1, max_length=200),
    kinds: str | None = Query(default=None, description="Comma-separated: application,document"),
) -> SearchResponse:
    requested_kinds = tuple(kinds.split(",")) if kinds is not None else _DEFAULT_KINDS

    results: list[ApplicationSearchResult | DocumentSearchResult] = []

    if "application" in requested_kinds:
        require_permission(user, Permission.READ_APPLICATION)
        for app in workspace.search_applications(user.tenant_id, q):
            results.append(ApplicationSearchResult(application=ApplicationResponse.from_model(app)))

    if "document" in requested_kinds:
        require_permission(user, Permission.READ_DOCUMENT)
        for doc in workspace.search_documents(user.tenant_id, q):
            results.append(
                DocumentSearchResult(
                    document_id=doc.id,
                    application_id=doc.application_id,
                    filename=doc.original_filename,
                    uploaded_at=doc.uploaded_at,
                )
            )

    return SearchResponse(query=q, results=results)
