"""
Application and Party REST endpoints — MIL API v1.

Endpoints:
    POST   /v1/applications                              Create application
    GET    /v1/applications                              List applications for the tenant
    GET    /v1/applications/{application_id}             Get application
    POST   /v1/applications/{application_id}/submit      Submit application for review
    POST   /v1/applications/{application_id}/withdraw    Withdraw application
    POST   /v1/applications/{application_id}/parties     Add party
    DELETE /v1/applications/{application_id}/parties/{party_id}  Remove party
    GET    /v1/applications/{application_id}/parties     List parties

Route handlers are intentionally thin:
    - Validate the request body (Pydantic does this automatically).
    - Extract the authenticated user from the dependency.
    - Delegate to the service.
    - Map the service result to a response schema.
    - Return the response.

No business logic lives here.

Dependency rule: imports from ``mil.api.deps``, ``mil.api.v1.schemas``,
``mil.kernel.types``, FastAPI, and the Python standard library only.
"""

from __future__ import annotations

from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, Query, status

from mil.api.deps import AppService, CurrentUser, FindingTriggerDep  # noqa: TC001
from mil.api.v1.schemas import (
    AddPartyRequest,
    ApplicationListResponse,
    ApplicationResponse,
    CreateApplicationRequest,
    PartyResponse,
)
from mil.kernel.types import ApplicationId, TenantId

router = APIRouter(prefix="/v1/applications", tags=["Applications"])


# ---------------------------------------------------------------------------
# Application CRUD
# ---------------------------------------------------------------------------


@router.post(
    "",
    summary="Create a new application",
    description=(
        "Register a new mortgage application in MIL in DRAFT state. "
        "Optionally supply a ``los_reference`` to associate this record with "
        "an existing Loan Origination System application. "
        "Requires ``write:application`` permission."
    ),
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        422: {"description": "Validation error"},
    },
)
def create_application(
    body: CreateApplicationRequest,
    user: CurrentUser,
    service: AppService,
) -> ApplicationResponse:
    """Create a new mortgage application in DRAFT state."""
    app = service.create_application(
        user,
        tenant_id=TenantId(user.tenant_id),
        los_reference=body.los_reference,
    )
    return ApplicationResponse.from_model(app)


@router.get(
    "",
    summary="List applications",
    description=(
        "Return all applications belonging to the authenticated user's tenant. "
        "Optionally filter by ``status``. Results are not paginated in Sprint 3D "
        "— the ``page`` and ``page_size`` parameters are accepted and echoed in "
        "the response for forward compatibility but do not slice the result set. "
        "Requires ``read:application`` permission."
    ),
    response_model=ApplicationListResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def list_applications(
    user: CurrentUser,
    service: AppService,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ApplicationListResponse:
    """Return applications for the authenticated tenant, optionally filtered by status."""
    apps = service.list_applications(
        user,
        tenant_id=TenantId(user.tenant_id),
        status=status_filter,
    )
    items = [ApplicationResponse.from_model(a) for a in apps]
    return ApplicationListResponse(
        items=items,
        total=len(items),
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{application_id}",
    summary="Get application",
    description=(
        "Retrieve a single mortgage application by its MIL identifier. "
        "Requires ``read:application`` permission."
    ),
    response_model=ApplicationResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Application not found"},
    },
)
def get_application(
    application_id: UUID,
    user: CurrentUser,
    service: AppService,
) -> ApplicationResponse:
    """Retrieve an application by ID."""
    app = service.get_application(user, application_id=ApplicationId(application_id))
    return ApplicationResponse.from_model(app)


# ---------------------------------------------------------------------------
# Application lifecycle actions
# ---------------------------------------------------------------------------


@router.post(
    "/{application_id}/submit",
    summary="Submit application for review",
    description=(
        "Advance the application from DRAFT to SUBMITTED status, signalling that "
        "the Relationship Manager has completed document upload and the application "
        "is ready for the intelligence review pipeline. "
        "At least one APPLICANT party must be registered before submission. "
        "Submission starts the Finding Generation workflow, which evaluates "
        "all evidence collected for the application (ADR-009). "
        "Requires ``write:application`` permission."
    ),
    response_model=ApplicationResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Application not found"},
        409: {"description": "No APPLICANT party registered"},
        422: {"description": "Application is not in DRAFT state"},
    },
)
def submit_application(
    application_id: UUID,
    user: CurrentUser,
    service: AppService,
    finding_trigger: FindingTriggerDep,
) -> ApplicationResponse:
    """Submit an application for intelligence review."""
    app = service.submit_application(user, application_id=ApplicationId(application_id))
    finding_trigger.trigger(app)
    return ApplicationResponse.from_model(app)


@router.post(
    "/{application_id}/withdraw",
    summary="Withdraw application",
    description=(
        "Transition the application to WITHDRAWN (terminal) state. "
        "A WITHDRAWN application cannot be re-activated. "
        "REVIEW_COMPLETE applications cannot be withdrawn. "
        "Requires ``write:application`` permission."
    ),
    response_model=ApplicationResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Application not found"},
        422: {"description": "Application is already in a terminal state"},
    },
)
def withdraw_application(
    application_id: UUID,
    user: CurrentUser,
    service: AppService,
) -> ApplicationResponse:
    """Withdraw an application."""
    app = service.withdraw_application(user, application_id=ApplicationId(application_id))
    return ApplicationResponse.from_model(app)


# ---------------------------------------------------------------------------
# Party sub-resource
# ---------------------------------------------------------------------------


@router.post(
    "/{application_id}/parties",
    summary="Add a party to an application",
    description=(
        "Register a new party (person or legal entity) against a mortgage "
        "application. Valid party types: APPLICANT, CO_APPLICANT, GUARANTOR, "
        "CORPORATE_ENTITY. The ``display_name`` is a non-PII label; full "
        "personal details live in the LOS and are never stored in MIL. "
        "Requires ``write:party`` permission."
    ),
    response_model=PartyResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Application not found"},
        422: {"description": "Invalid party_type or display_name"},
    },
)
def add_party(
    application_id: UUID,
    body: AddPartyRequest,
    user: CurrentUser,
    service: AppService,
) -> PartyResponse:
    """Add a party to the application."""
    party = service.add_party_by_type_string(
        user,
        application_id=ApplicationId(application_id),
        party_type_str=body.party_type,
        display_name=body.display_name,
    )
    return PartyResponse.from_model(party)


@router.delete(
    "/{application_id}/parties/{party_id}",
    summary="Remove a party from an application",
    description=(
        "Remove a party from a mortgage application. The application must not "
        "be in a terminal state (WITHDRAWN or REVIEW_COMPLETE). "
        "Requires ``write:party`` permission."
    ),
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Application or party not found"},
        422: {"description": "Application is in a terminal state"},
    },
)
def remove_party(
    application_id: UUID,
    party_id: UUID,
    user: CurrentUser,
    service: AppService,
) -> None:
    """Remove a party from the application."""
    service.remove_party(
        user,
        application_id=ApplicationId(application_id),
        party_id=party_id,
    )


@router.get(
    "/{application_id}/parties",
    summary="List parties on an application",
    description=(
        "Return all parties registered against a mortgage application. "
        "Requires ``read:party`` permission."
    ),
    response_model=list[PartyResponse],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Application not found"},
    },
)
def list_parties(
    application_id: UUID,
    user: CurrentUser,
    service: AppService,
) -> list[PartyResponse]:
    """Return all parties for the application."""
    app = service.get_application(user, application_id=ApplicationId(application_id))
    return [PartyResponse.from_model(p) for p in app.parties]
