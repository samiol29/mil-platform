"""
Evidence REST endpoints — MIL API v1.

Endpoints:
    GET /v1/applications/{application_id}/evidence   List evidence items for an application

Route handlers are intentionally thin: delegate to ``EvidenceService``, map
the result to a response schema, return it. No business logic lives here.

Dependency rule: imports from ``mil.api.deps``, ``mil.api.v1.schemas``,
``mil.kernel.types``, FastAPI, and the Python standard library only.
"""

from __future__ import annotations

from uuid import UUID  # noqa: TC003

from fastapi import APIRouter

from mil.api.deps import CurrentUser, EvidenceServiceDep  # noqa: TC001
from mil.api.v1.schemas import EvidenceItemResponse
from mil.kernel.types import ApplicationId

router = APIRouter(prefix="/v1/applications", tags=["Evidence"])


@router.get(
    "/{application_id}/evidence",
    summary="List evidence items for an application",
    description=(
        "Return every evidence item extracted for an application, most "
        "recent first. Every item carries its full provenance (source "
        "document, page, field location, extraction method/version, "
        "confidence band) per Constitution Principle II. "
        "Requires ``read:evidence`` permission."
    ),
    response_model=list[EvidenceItemResponse],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def list_evidence(
    application_id: UUID,
    user: CurrentUser,
    service: EvidenceServiceDep,
) -> list[EvidenceItemResponse]:
    """Return all evidence items for an application."""
    items = service.list_for_application(user, application_id=ApplicationId(application_id))
    return [EvidenceItemResponse.from_model(item) for item in items]
