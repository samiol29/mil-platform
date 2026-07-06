"""
Audit REST endpoints — MIL API v1.

Endpoints:
    GET /v1/applications/{application_id}/audit   Chronological audit trail for an application

Read-only: no mutation endpoint exists in this router, and none is planned —
every audit event is written exclusively by ``AuditWriter`` from within the
bounded context that produced it (Constitution Principle VIII).

Dependency rule: imports from ``mil.api.deps``, ``mil.api.v1.schemas``,
``mil.kernel.security``, FastAPI, and the Python standard library only.
"""

from __future__ import annotations

from uuid import UUID  # noqa: TC003

from fastapi import APIRouter

from mil.api.deps import AuditRepositoryDep, CurrentUser  # noqa: TC001
from mil.api.v1.schemas import AuditEventResponse
from mil.kernel.security import Permission, require_permission

router = APIRouter(prefix="/v1/applications", tags=["Audit"])


@router.get(
    "/{application_id}/audit",
    summary="Get the audit trail for an application",
    description=(
        "Return every audit event recorded for an application, in true "
        "chronological order (by the append-only log's monotonic sequence "
        "number). Read-only — this endpoint exposes no mutation. "
        "Requires ``read:audit`` permission."
    ),
    response_model=list[AuditEventResponse],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_audit_trail(
    application_id: UUID,
    user: CurrentUser,
    repository: AuditRepositoryDep,
) -> list[AuditEventResponse]:
    """Return the full, ordered audit trail for an application."""
    require_permission(user, Permission.READ_AUDIT)
    events = repository.get_for_application(application_id)
    return [AuditEventResponse.from_model(event) for event in events]
