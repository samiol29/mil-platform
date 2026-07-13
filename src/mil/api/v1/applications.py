"""
Application and Party REST endpoints — MIL API v1.

Endpoints:
    POST   /v1/applications                              Create application
    GET    /v1/applications                              List applications for the tenant
    GET    /v1/applications/{application_id}             Get application
    POST   /v1/applications/{application_id}/submit      Submit application for review
    GET    /v1/applications/{application_id}/evaluation  Get real FINDING_GENERATION run status
    POST   /v1/applications/{application_id}/retry-evaluation  Retry a FAILED evaluation run
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

from mil.api.deps import (  # noqa: TC001
    AppService,
    AssignmentServiceDep,
    CurrentUser,
    FindingTriggerDep,
    ReviewServiceDep,
)
from mil.api.v1.schemas import (
    AddPartyRequest,
    ApplicationListResponse,
    ApplicationResponse,
    CreateApplicationRequest,
    EvaluationStatusResponse,
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
        "an existing Loan Origination System application, and/or a "
        "``loan_number`` (the lender's own loan identifier, distinct from "
        "``los_reference``). "
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
        loan_number=body.loan_number,
    )
    return ApplicationResponse.from_model(app)


@router.get(
    "",
    summary="List applications",
    description=(
        "Return all applications belonging to the authenticated user's tenant. "
        "Optionally filter by ``status``, and/or ``search`` — a case-insensitive "
        "substring match against LOS reference, loan number, application ID, or "
        "a registered party's display name. Existing clients that omit "
        "``search`` are unaffected: the parameter is optional and additive. "
        "``assigned_to_me`` (final product polish sprint, A1) restricts results "
        "to applications where the caller is the owner or reviewer — requires "
        "``manage:assignment``. ``escalated`` restricts results to applications "
        "with at least one Finding currently escalated to the caller's role or "
        "to them specifically — requires ``read:application``. Both compose "
        "with ``status``/``search`` (AND, not OR). "
        "Results are not paginated in Sprint 3D "
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
    assignments: AssignmentServiceDep,
    reviews: ReviewServiceDep,
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=255,
        description=(
            "Case-insensitive substring match against LOS reference, loan "
            "number, application ID, or borrower display name."
        ),
    ),
    assigned_to_me: bool = Query(
        default=False,
        description="Restrict to applications the caller owns or reviews.",
    ),
    escalated: bool = Query(
        default=False,
        description=(
            "Restrict to applications with a Finding currently escalated to "
            "the caller's role or to them specifically."
        ),
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ApplicationListResponse:
    """Return applications for the authenticated tenant, optionally filtered by status/search."""
    apps = service.list_applications(
        user,
        tenant_id=TenantId(user.tenant_id),
        status=status_filter,
        search=search,
    )
    if assigned_to_me:
        assigned_ids = {a.application_id for a in assignments.get_assigned_to_me(user)}
        apps = [a for a in apps if a.id in assigned_ids]
    if escalated:
        escalated_ids = {s.application_id for s in reviews.get_escalated_for_caller(user)}
        apps = [a for a in apps if a.id in escalated_ids]
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


@router.get(
    "/{application_id}/evaluation",
    summary="Get the application's evaluation (Finding Generation) status",
    description=(
        "Return the real status of the application's FINDING_GENERATION "
        "workflow run — NOT_TRIGGERED if evaluation was never started (e.g. "
        "the application has not been submitted), or the run's actual "
        "PENDING/RUNNING/COMPLETED/FAILED status. Distinguishes 'no findings "
        "because evaluation never ran or failed' from 'no findings because "
        "the application is genuinely clean' — never inferred from document "
        "processing status alone. Requires ``read:application`` permission."
    ),
    response_model=EvaluationStatusResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Application not found"},
    },
)
def get_evaluation_status(
    application_id: UUID,
    user: CurrentUser,
    service: AppService,
    finding_trigger: FindingTriggerDep,
) -> EvaluationStatusResponse:
    """Return the application's real FINDING_GENERATION run status."""
    app = service.get_application(user, application_id=ApplicationId(application_id))
    run = finding_trigger.latest_run(app)
    if run is None:
        return EvaluationStatusResponse(status="NOT_TRIGGERED")

    error_message = None
    if run.status == "FAILED":
        failed_step = next((s for s in run.steps if s.status == "FAILED"), None)
        error_message = failed_step.error_message if failed_step else None

    return EvaluationStatusResponse(
        status=run.status,
        error_message=error_message,
        retryable=run.status == "FAILED",
        started_at=run.created_at,
        completed_at=run.completed_at,
    )


@router.post(
    "/{application_id}/retry-evaluation",
    summary="Retry a failed evaluation (Finding Generation)",
    description=(
        "Re-run Finding Generation -> Policy Evaluation -> Review handoff for "
        "an application whose most recent evaluation run ended in FAILED "
        "(e.g. an AI provider outage). Only available when the real run "
        "status is FAILED — retrying a run still in flight, or one that "
        "never started or already succeeded, is rejected. "
        "Requires ``write:application`` permission."
    ),
    response_model=ApplicationResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Application not found"},
        409: {"description": "No FAILED evaluation run exists to retry"},
    },
)
def retry_evaluation(
    application_id: UUID,
    user: CurrentUser,
    service: AppService,
    finding_trigger: FindingTriggerDep,
) -> ApplicationResponse:
    """Retry evaluation for an application whose last run FAILED."""
    app = service.get_application(user, application_id=ApplicationId(application_id))
    finding_trigger.retry(user, app)
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
