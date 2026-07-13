"""
Assignment REST endpoints — MIL API v1 (spec 005-enterprise-platform §1,
Wave 2 — RM/Banker Workspace).

Endpoints:
    PUT    /v1/applications/{application_id}/assignment          Create/update the assignment
    GET    /v1/applications/{application_id}/assignment           Get the current assignment
    GET    /v1/applications/{application_id}/assignment-history   List assignment history
    GET    /v1/rm/portfolio                                       The caller's own portfolio

Route handlers are thin; `AssignmentService`'s methods self-check
`manage:assignment` permission.

Dependency rule: imports from `mil.api.deps`, `mil.api.v1.schemas`, FastAPI,
and the Python standard library only.
"""

from __future__ import annotations

from uuid import UUID  # noqa: TC003

from fastapi import APIRouter

from mil.api.deps import AssignmentServiceDep, CurrentUser, RmWorkspaceDep  # noqa: TC001
from mil.api.v1.schemas import (
    ApplicationResponse,
    AssignmentHistoryListResponse,
    AssignmentHistoryResponse,
    AssignmentResponse,
    PortfolioResponse,
    SetAssignmentRequest,
)

router = APIRouter(prefix="/v1/applications/{application_id}", tags=["Assignment"])
portfolio_router = APIRouter(prefix="/v1/rm", tags=["Assignment"])


@router.put(
    "/assignment",
    summary="Create or update an application's assignment (owner/reviewer)",
    response_model=AssignmentResponse,
    responses={403: {"description": "Insufficient permissions"}},
)
def set_assignment(
    application_id: UUID,
    body: SetAssignmentRequest,
    user: CurrentUser,
    service: AssignmentServiceDep,
) -> AssignmentResponse:
    assignment = service.set_assignment(
        user,
        application_id=application_id,
        tenant_id=user.tenant_id,
        owner_user_id=body.owner_user_id,
        reviewer_user_id=body.reviewer_user_id,
    )
    return AssignmentResponse(
        id=assignment.id,
        application_id=assignment.application_id,
        owner_user_id=assignment.owner_user_id,
        reviewer_user_id=assignment.reviewer_user_id,
        assigned_by_user_id=assignment.assigned_by_user_id,
        assigned_at=assignment.assigned_at,
    )


@router.get(
    "/assignment",
    summary="Get an application's current assignment",
    response_model=AssignmentResponse | None,
)
def get_assignment(
    application_id: UUID, user: CurrentUser, service: AssignmentServiceDep
) -> AssignmentResponse | None:
    assignment = service.get_assignment(user, application_id)
    if assignment is None:
        return None
    return AssignmentResponse(
        id=assignment.id,
        application_id=assignment.application_id,
        owner_user_id=assignment.owner_user_id,
        reviewer_user_id=assignment.reviewer_user_id,
        assigned_by_user_id=assignment.assigned_by_user_id,
        assigned_at=assignment.assigned_at,
    )


@router.get(
    "/assignment-history",
    summary="List an application's assignment history",
    response_model=AssignmentHistoryListResponse,
)
def get_assignment_history(
    application_id: UUID, user: CurrentUser, service: AssignmentServiceDep
) -> AssignmentHistoryListResponse:
    history = service.get_history(user, application_id)
    return AssignmentHistoryListResponse(
        items=[
            AssignmentHistoryResponse(
                id=h.id,
                application_id=h.application_id,
                owner_user_id=h.owner_user_id,
                reviewer_user_id=h.reviewer_user_id,
                assigned_by_user_id=h.assigned_by_user_id,
                assigned_at=h.assigned_at,
                created_at=h.created_at,
            )
            for h in history
        ]
    )


@portfolio_router.get(
    "/portfolio",
    summary="The caller's own portfolio of owned applications",
    response_model=PortfolioResponse,
)
def get_portfolio(user: CurrentUser, workspace: RmWorkspaceDep) -> PortfolioResponse:
    applications = workspace.get_portfolio(user)
    return PortfolioResponse(items=[ApplicationResponse.from_model(app) for app in applications])
