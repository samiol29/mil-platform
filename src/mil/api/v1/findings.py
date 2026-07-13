"""
Finding REST endpoints — MIL API v1.

Endpoints:
    GET  /v1/applications/{application_id}/findings   List findings for an application
    GET  /v1/findings/escalated                        List findings escalated to the caller
    POST /v1/findings/{finding_id}/verify              Verify (approve) a finding
    POST /v1/findings/{finding_id}/override             Override a finding
    POST /v1/findings/{finding_id}/escalate             Escalate a finding to another role

Route handlers are intentionally thin: delegate to ``FindingService`` /
``FindingReviewActions``, map the result to a response schema, return it.

**Escalation** (spec 002 FR-054) was implemented after a focused domain-design
review (see ``HANDOFF.md``): ``ESCALATED`` is a non-terminal Review Session
status that transfers ownership to another role's (or, optionally, a
specific person's) queue; the existing verify/override actions resolve it —
there is no separate "resolve escalation" action or bounded context.
``FindingReviewActions._authorize_resolution`` enforces that only a holder
of the target role (or the specifically assigned person, when one is set)
may resolve an escalated finding.

Dependency rule: imports from ``mil.api.deps``, ``mil.api.v1.schemas``,
``mil.kernel.types``, FastAPI, and the Python standard library only.
"""

from __future__ import annotations

from uuid import UUID  # noqa: TC003

from fastapi import APIRouter

from mil.api.deps import (  # noqa: TC001
    CurrentUser,
    FindingReviewActionsDep,
    FindingServiceDep,
    ReviewServiceDep,
)
from mil.api.v1.schemas import EscalateFindingRequest, FindingResponse, OverrideFindingRequest
from mil.kernel.errors import NotFoundError
from mil.kernel.types import ApplicationId, FindingId

router = APIRouter(tags=["Findings"])

_VERIFIED_STATUS = "APPROVED"
_OVERRIDDEN_STATUS = "OVERRIDDEN"
_ESCALATED_STATUS = "ESCALATED"


def _finding_state(review_status: str | None) -> str:
    """
    Map a Review Session status onto the Underwriter Workspace's Finding
    lifecycle vocabulary (spec 002 data-model.md: unreviewed / verified /
    overridden / escalated). No session yet, or a non-terminal
    (``PENDING_REVIEW``/``IN_REVIEW``) status, maps to ``"unreviewed"``. A
    ``REJECTED`` session status — a real Review Session state with no
    defined Underwriter Workspace equivalent, see ``HANDOFF.md`` —
    deliberately falls back to ``"unreviewed"`` rather than
    ``"verified"``/``"overridden"``: the conservative failure mode for a
    compliance-sensitive review state is to keep a finding visibly in the
    reviewer's queue, never to imply a resolution that did not happen
    through this workspace.
    """
    if review_status == _VERIFIED_STATUS:
        return "verified"
    if review_status == _OVERRIDDEN_STATUS:
        return "overridden"
    if review_status == _ESCALATED_STATUS:
        return "escalated"
    return "unreviewed"


@router.get(
    "/v1/applications/{application_id}/findings",
    summary="List findings for an application",
    description=(
        "Return every finding generated for an application, most recent "
        "first, each with resolved evidence references and its current "
        "review state. All five explainability fields and all four "
        "attribution fields are always present. "
        "Requires ``read:findings`` permission."
    ),
    response_model=list[FindingResponse],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def list_findings(
    application_id: UUID,
    user: CurrentUser,
    service: FindingServiceDep,
    actions: FindingReviewActionsDep,
) -> list[FindingResponse]:
    """Return all findings for an application, with resolved state and policy attribution."""
    findings = service.list_for_application(user, application_id=ApplicationId(application_id))
    responses = []
    for finding in findings:
        session = actions.get_review_session(finding.id)
        responses.append(
            FindingResponse.from_model(
                finding,
                state=_finding_state(session.status if session is not None else None),
                policy_version=actions.policy_version_for(finding.id),
                escalated_to_role=session.escalated_to_role if session is not None else None,
                escalated_to_user_id=session.escalated_to_user_id if session is not None else None,
            )
        )
    return responses


@router.get(
    "/v1/findings/escalated",
    summary="List findings currently escalated to the caller",
    description=(
        "Return every finding whose Review Session is currently ESCALATED "
        "to a role the caller holds, or specifically to the caller — the "
        "caller's escalation queue (final product polish sprint, A5). "
        "Before this, an escalated finding was only discoverable by opening "
        "the specific application it belonged to (via a notification, or by "
        "chance). Requires ``read:application`` permission."
    ),
    response_model=list[FindingResponse],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def list_escalated_findings(
    user: CurrentUser,
    service: FindingServiceDep,
    actions: FindingReviewActionsDep,
    reviews: ReviewServiceDep,
) -> list[FindingResponse]:
    """Return every finding currently escalated to the caller's role or to them specifically."""
    sessions = reviews.get_escalated_for_caller(user)
    responses = []
    for session in sessions:
        finding = service.get_by_id(user, finding_id=FindingId(session.finding_id))
        if finding is None:
            continue
        responses.append(
            FindingResponse.from_model(
                finding,
                state=_finding_state(session.status),
                policy_version=actions.policy_version_for(finding.id),
                escalated_to_role=session.escalated_to_role,
                escalated_to_user_id=session.escalated_to_user_id,
            )
        )
    return responses


@router.post(
    "/v1/findings/{finding_id}/verify",
    summary="Verify a finding",
    description=(
        "Record a human verification of a finding (idempotent, attributed, "
        "immutable — Constitution Principle VIII). Requires an existing "
        "Review Session for the finding (created automatically once policy "
        "evaluation completes) and ``verify:finding`` permission."
    ),
    response_model=FindingResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Finding or its Review Session not found"},
        422: {"description": "The Review Session is not in a state that allows verification"},
    },
)
def verify_finding(
    finding_id: UUID,
    user: CurrentUser,
    service: FindingServiceDep,
    actions: FindingReviewActionsDep,
) -> FindingResponse:
    """Verify (approve) the finding under review."""
    finding = service.get_by_id(user, finding_id=FindingId(finding_id))
    if finding is None:
        raise NotFoundError("Finding", finding_id)

    session = actions.verify(user, finding_id)
    return FindingResponse.from_model(
        finding,
        state=_finding_state(session.status),
        policy_version=actions.policy_version_for(finding_id),
        escalated_to_role=session.escalated_to_role,
        escalated_to_user_id=session.escalated_to_user_id,
    )


@router.post(
    "/v1/findings/{finding_id}/override",
    summary="Override a finding",
    description=(
        "Record a human override of a finding, requiring a non-empty "
        "reason (idempotent, attributed, immutable — Constitution "
        "Principle VIII). Requires an existing Review Session for the "
        "finding and ``override:finding`` permission."
    ),
    response_model=FindingResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Finding or its Review Session not found"},
        422: {"description": "Missing reason/new value, or an invalid Review Session state"},
    },
)
def override_finding(
    finding_id: UUID,
    body: OverrideFindingRequest,
    user: CurrentUser,
    service: FindingServiceDep,
    actions: FindingReviewActionsDep,
) -> FindingResponse:
    """Override the finding under review."""
    finding = service.get_by_id(user, finding_id=FindingId(finding_id))
    if finding is None:
        raise NotFoundError("Finding", finding_id)

    session = actions.override(
        user,
        finding_id,
        reason=body.reason,
        previous_value=body.previous_value,
        new_value=body.new_value,
    )
    return FindingResponse.from_model(
        finding,
        state=_finding_state(session.status),
        policy_version=actions.policy_version_for(finding_id),
        escalated_to_role=session.escalated_to_role,
        escalated_to_user_id=session.escalated_to_user_id,
    )


@router.post(
    "/v1/findings/{finding_id}/escalate",
    summary="Escalate a finding",
    description=(
        "Escalate a finding to another role's (or, optionally, a specific "
        "person's) queue, requiring a non-empty reason (spec 002 FR-054). "
        "Non-terminal: the escalated finding is resolved by the existing "
        "verify/override actions, restricted to the target role (or "
        "person). Requires ``escalate:finding`` permission."
    ),
    response_model=FindingResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Finding or its Review Session not found"},
        422: {"description": "Missing reason/target role, or an invalid Review Session state"},
    },
)
def escalate_finding(
    finding_id: UUID,
    body: EscalateFindingRequest,
    user: CurrentUser,
    service: FindingServiceDep,
    actions: FindingReviewActionsDep,
) -> FindingResponse:
    """Escalate the finding under review to another role's queue."""
    finding = service.get_by_id(user, finding_id=FindingId(finding_id))
    if finding is None:
        raise NotFoundError("Finding", finding_id)

    session = actions.escalate(
        user,
        finding_id,
        reason=body.reason,
        target_role=body.target_role,
        target_user_id=body.target_user_id,
    )
    return FindingResponse.from_model(
        finding,
        state=_finding_state(session.status),
        policy_version=actions.policy_version_for(finding_id),
        escalated_to_role=session.escalated_to_role,
        escalated_to_user_id=session.escalated_to_user_id,
    )
