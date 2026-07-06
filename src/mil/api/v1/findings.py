"""
Finding REST endpoints — MIL API v1.

Endpoints:
    GET  /v1/applications/{application_id}/findings   List findings for an application
    POST /v1/findings/{finding_id}/verify              Verify (approve) a finding
    POST /v1/findings/{finding_id}/override             Override a finding

Route handlers are intentionally thin: delegate to ``FindingService`` /
``FindingReviewActions``, map the result to a response schema, return it.

**Escalation is deliberately not implemented here.** Spec 002 FR-054
requires a third action, escalation, alongside verify/override — but no
backend domain logic for it exists yet (the Review bounded context's own
module docstring states escalation is "out of scope for this sprint," and
defines no corresponding ``ReviewStatus``, action type, or transition rule).
Implementing it requires a genuine state-machine design decision (what does
"escalate" transition to, does it close the review or leave it open for
reassignment, how is a target role recorded and attributed) that is not
this router's call to make unilaterally. See ``HANDOFF.md`` for the full
analysis and the concrete options presented for that decision.

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
)
from mil.api.v1.schemas import FindingResponse, OverrideFindingRequest
from mil.kernel.errors import NotFoundError
from mil.kernel.types import ApplicationId, FindingId, UserId

router = APIRouter(tags=["Findings"])

_VERIFIED_STATUS = "APPROVED"
_OVERRIDDEN_STATUS = "OVERRIDDEN"


def _finding_state(review_status: str | None) -> str:
    """
    Map a Review Session status onto the Underwriter Workspace's Finding
    lifecycle vocabulary (spec 002 data-model.md: unreviewed / verified /
    overridden). No session yet, or a non-terminal status, maps to
    ``"unreviewed"``. A ``REJECTED`` session status — a real Review Session
    state with no defined Underwriter Workspace equivalent, see
    ``HANDOFF.md`` — deliberately falls back to ``"unreviewed"`` rather
    than ``"verified"``/``"overridden"``: the conservative failure mode for
    a compliance-sensitive review state is to keep a finding visibly in the
    reviewer's queue, never to imply a resolution that did not happen
    through this workspace.
    """
    if review_status == _VERIFIED_STATUS:
        return "verified"
    if review_status == _OVERRIDDEN_STATUS:
        return "overridden"
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
    return [
        FindingResponse.from_model(
            finding,
            state=_finding_state(actions.get_review_status(finding.id)),
            policy_version=actions.policy_version_for(finding.id),
        )
        for finding in findings
    ]


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

    session = actions.verify(finding_id, actor_user_id=UserId(user.user_id))
    return FindingResponse.from_model(
        finding,
        state=_finding_state(session.status),
        policy_version=actions.policy_version_for(finding_id),
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
        finding_id,
        actor_user_id=UserId(user.user_id),
        reason=body.reason,
        previous_value=body.previous_value,
        new_value=body.new_value,
    )
    return FindingResponse.from_model(
        finding,
        state=_finding_state(session.status),
        policy_version=actions.policy_version_for(finding_id),
    )
