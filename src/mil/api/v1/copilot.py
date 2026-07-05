"""
Copilot REST endpoints — MIL API v1 (US2 Sprint 7C).

Endpoints:
    POST   /v1/copilot/query                              Ask a question, get a grounded response
    GET    /v1/copilot/sessions/{session_id}               Get session metadata
    GET    /v1/copilot/sessions/{session_id}/history        Get ordered query/response history
    GET    /v1/applications/{application_id}/copilot        Get the latest session for an application

Route handlers are intentionally thin:
    - Validate the request body (Pydantic does this automatically).
    - Extract the authenticated user from the dependency.
    - Delegate to ``CopilotService`` (which enforces ``query:copilot``
      permission and tenant isolation itself — routes never check permissions
      or tenant scope directly).
    - Map the service result to a response schema.
    - Return the response.

No business logic lives here. Two ``APIRouter`` instances are defined: one
top-level (``router``, prefix ``/v1/copilot``) for session/query resources
addressed by their own id, and one nested under the application resource
(``application_copilot_router``) — mirroring how ``documents.py`` nests under
``/v1/applications/{application_id}/documents``.

Dependency rule: imports from ``mil.api.deps``, ``mil.api.v1.schemas``,
FastAPI, and the Python standard library only.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, status

from mil.api.deps import CopilotServiceDep, CurrentUser  # noqa: TC001
from mil.api.v1.schemas import (
    CopilotHistoryItem,
    CopilotHistoryResponse,
    CopilotQueryRequest,
    CopilotResponseSchema,
    CopilotSessionResponse,
)
from mil.kernel.types import TenantId

router = APIRouter(prefix="/v1/copilot", tags=["Copilot"])
application_copilot_router = APIRouter(
    prefix="/v1/applications/{application_id}/copilot", tags=["Copilot"]
)


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


@router.post(
    "/query",
    summary="Ask the Copilot a question about an application",
    description=(
        "Creates (or resumes, via ``session_id``) an application-scoped Copilot "
        "session, records the reviewer's question, generates a grounded response "
        "using only governed records for the application (Evidence, Findings, "
        "PolicyResults, Review history), and returns the response with its "
        "citations, prompt version, and model version. Prompt selection is "
        "rule-based and deterministic (no AI classifier). If insufficient "
        "governed data exists, or the model's answer cannot be grounded in a "
        "citation, a safe 'insufficient grounding' response is returned instead "
        "of a fabricated answer (ADR-011). Requires ``query:copilot`` permission."
    ),
    response_model=CopilotResponseSchema,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Application or session not found"},
        422: {
            "description": (
                "Validation error, or the application does not belong to the caller's tenant"
            )
        },
    },
)
def submit_copilot_query(
    body: CopilotQueryRequest,
    user: CurrentUser,
    service: CopilotServiceDep,
) -> CopilotResponseSchema:
    """Submit a question and return a grounded Copilot response."""
    session = service.start_or_resume_session(
        user,
        application_id=body.application_id,
        tenant_id=TenantId(user.tenant_id),
        created_by_user_id=user.user_id,
        session_id=body.session_id,
        correlation_id=str(uuid4()),
    )
    query = service.submit_query(
        user,
        session,
        question_text=body.question,
        asked_by_user_id=user.user_id,
    )
    response = service.generate_response(user, session, query)
    return CopilotResponseSchema.from_model(response, session_id=session.id)


# ---------------------------------------------------------------------------
# Session metadata and history
# ---------------------------------------------------------------------------


@router.get(
    "/sessions/{session_id}",
    summary="Get Copilot session metadata",
    description=(
        "Retrieve metadata for a Copilot session by its identifier, scoped to "
        "the caller's tenant. Requires ``query:copilot`` permission."
    ),
    response_model=CopilotSessionResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Session not found"},
    },
)
def get_copilot_session(
    session_id: UUID,
    user: CurrentUser,
    service: CopilotServiceDep,
) -> CopilotSessionResponse:
    """Retrieve a Copilot session by ID."""
    session = service.get_session(user, session_id)
    return CopilotSessionResponse.from_model(session)


@router.get(
    "/sessions/{session_id}/history",
    summary="Get the ordered query/response history for a Copilot session",
    description=(
        "Return every query submitted on this session, each paired with its "
        "response (if generated), oldest first. Retrieving a response here "
        "records a synchronous ``COPILOT_RESPONSE_VIEWED`` audit event. "
        "Requires ``query:copilot`` permission."
    ),
    response_model=CopilotHistoryResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Session not found"},
    },
)
def get_copilot_history(
    session_id: UUID,
    user: CurrentUser,
    service: CopilotServiceDep,
) -> CopilotHistoryResponse:
    """Retrieve the ordered query/response history for a session."""
    session = service.get_session(user, session_id)
    history = service.get_history(user, session)
    items = [
        CopilotHistoryItem(
            query_id=query.id,
            question=query.question_text,
            asked_by_user_id=query.asked_by_user_id,
            asked_at=query.created_at,
            response=(
                CopilotResponseSchema.from_model(response, session_id=session.id)
                if response is not None
                else None
            ),
        )
        for query, response in history
    ]
    return CopilotHistoryResponse(session_id=session.id, items=items)


# ---------------------------------------------------------------------------
# Latest session for an application
# ---------------------------------------------------------------------------


@application_copilot_router.get(
    "",
    summary="Get the latest Copilot session for an application",
    description=(
        "Return the most recently created Copilot session for this application. "
        "Requires ``query:copilot`` permission."
    ),
    response_model=CopilotSessionResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Application not found, or no Copilot session exists yet"},
        422: {"description": "The application does not belong to the caller's tenant"},
    },
)
def get_latest_copilot_session(
    application_id: UUID,
    user: CurrentUser,
    service: CopilotServiceDep,
) -> CopilotSessionResponse:
    """Retrieve the latest Copilot session for an application."""
    session = service.get_latest_session_for_application(
        user, application_id, tenant_id=TenantId(user.tenant_id)
    )
    return CopilotSessionResponse.from_model(session)
