"""
Borrower Identity Resolution REST endpoints — MIL API v1 (spec 005-
enterprise-platform §5, Wave 3).

Endpoints:
    POST /v1/parties/{party_id}/compute-match-candidates   Compute + persist candidates
    GET  /v1/parties/{party_id}/match-candidates            List candidates for a party
    GET  /v1/parties/{party_id}/borrower-identity           The party's resolved identity, if any
    POST /v1/match-candidates/{candidate_id}/confirm        Confirm a match (creates/extends identity)
    POST /v1/match-candidates/{candidate_id}/reject         Reject a match
    GET  /v1/borrower-identities/{identity_id}              Get a resolved identity
    GET  /v1/borrower-identities/{identity_id}/members      List a resolved identity's members

Route handlers are thin; `BorrowerIdentityService`'s methods self-check
`read:cross_application_identity`/`confirm:identity_match` permissions.

Dependency rule: imports from `mil.api.deps`, `mil.api.v1.schemas`, FastAPI,
and the Python standard library only.
"""

from __future__ import annotations

from uuid import UUID  # noqa: TC003

from fastapi import APIRouter

from mil.api.deps import (  # noqa: TC001
    BorrowerIdentityWorkspaceDep,
    CrossApplicationIntelligenceWorkspaceDep,
    CurrentUser,
)
from mil.api.v1.schemas import (
    BorrowerIdentityMemberListResponse,
    BorrowerIdentityMemberResponse,
    BorrowerIdentityResponse,
    CrossApplicationObservationResponse,
    CrossApplicationSignalListResponse,
    IdentityMatchCandidateListResponse,
    IdentityMatchCandidateResponse,
    RejectMatchRequest,
)

router = APIRouter(tags=["Borrower Identity"])


def _candidate_response(candidate: object) -> IdentityMatchCandidateResponse:
    return IdentityMatchCandidateResponse(
        id=candidate.id,  # type: ignore[attr-defined]
        tenant_id=candidate.tenant_id,  # type: ignore[attr-defined]
        party_id=candidate.party_id,  # type: ignore[attr-defined]
        candidate_party_id=candidate.candidate_party_id,  # type: ignore[attr-defined]
        match_score=float(candidate.match_score),  # type: ignore[attr-defined]
        match_basis=candidate.match_basis,  # type: ignore[attr-defined]
        status=candidate.status,  # type: ignore[attr-defined]
        reviewed_by_user_id=candidate.reviewed_by_user_id,  # type: ignore[attr-defined]
        reason=candidate.reason,  # type: ignore[attr-defined]
        reviewed_at=candidate.reviewed_at,  # type: ignore[attr-defined]
        created_at=candidate.created_at,  # type: ignore[attr-defined]
    )


def _identity_response(identity: object) -> BorrowerIdentityResponse:
    return BorrowerIdentityResponse(
        id=identity.id,  # type: ignore[attr-defined]
        tenant_id=identity.tenant_id,  # type: ignore[attr-defined]
        primary_display_name=identity.primary_display_name,  # type: ignore[attr-defined]
        created_at=identity.created_at,  # type: ignore[attr-defined]
    )


def _member_response(member: object) -> BorrowerIdentityMemberResponse:
    return BorrowerIdentityMemberResponse(
        id=member.id,  # type: ignore[attr-defined]
        borrower_identity_id=member.borrower_identity_id,  # type: ignore[attr-defined]
        party_id=member.party_id,  # type: ignore[attr-defined]
        application_id=member.application_id,  # type: ignore[attr-defined]
        linked_by_user_id=member.linked_by_user_id,  # type: ignore[attr-defined]
        linked_at=member.linked_at,  # type: ignore[attr-defined]
        unlinked_at=member.unlinked_at,  # type: ignore[attr-defined]
        unlinked_by_user_id=member.unlinked_by_user_id,  # type: ignore[attr-defined]
    )


@router.post(
    "/v1/parties/{party_id}/compute-match-candidates",
    summary="Compute and persist identity match candidates for a party",
    response_model=IdentityMatchCandidateListResponse,
    responses={403: {"description": "Insufficient permissions"}, 404: {"description": "Party not found"}},
)
def compute_match_candidates(
    party_id: UUID, user: CurrentUser, workspace: BorrowerIdentityWorkspaceDep
) -> IdentityMatchCandidateListResponse:
    candidates = workspace.compute_candidates(user, party_id)
    return IdentityMatchCandidateListResponse(items=[_candidate_response(c) for c in candidates])


@router.get(
    "/v1/parties/{party_id}/match-candidates",
    summary="List identity match candidates suggested for a party",
    response_model=IdentityMatchCandidateListResponse,
)
def list_match_candidates(
    party_id: UUID, user: CurrentUser, workspace: BorrowerIdentityWorkspaceDep
) -> IdentityMatchCandidateListResponse:
    candidates = workspace.get_candidates_for_party(user, party_id)
    return IdentityMatchCandidateListResponse(items=[_candidate_response(c) for c in candidates])


@router.get(
    "/v1/parties/{party_id}/borrower-identity",
    summary="Get a party's resolved borrower identity, if one exists",
    response_model=BorrowerIdentityResponse | None,
)
def get_identity_for_party(
    party_id: UUID, user: CurrentUser, workspace: BorrowerIdentityWorkspaceDep
) -> BorrowerIdentityResponse | None:
    identity = workspace.get_identity_for_party(user, party_id)
    if identity is None:
        return None
    return _identity_response(identity)


@router.post(
    "/v1/match-candidates/{candidate_id}/confirm",
    summary="Confirm an identity match candidate (creates/extends a BorrowerIdentity)",
    response_model=BorrowerIdentityResponse,
    responses={403: {"description": "Insufficient permissions"}, 404: {"description": "Candidate not found"}},
)
def confirm_match(
    candidate_id: UUID, user: CurrentUser, workspace: BorrowerIdentityWorkspaceDep
) -> BorrowerIdentityResponse:
    identity = workspace.confirm_match(user, candidate_id)
    return _identity_response(identity)


@router.post(
    "/v1/match-candidates/{candidate_id}/reject",
    summary="Reject an identity match candidate",
    response_model=IdentityMatchCandidateResponse,
    responses={403: {"description": "Insufficient permissions"}, 404: {"description": "Candidate not found"}},
)
def reject_match(
    candidate_id: UUID,
    body: RejectMatchRequest,
    user: CurrentUser,
    workspace: BorrowerIdentityWorkspaceDep,
) -> IdentityMatchCandidateResponse:
    candidate = workspace.reject_match(user, candidate_id, body.reason)
    return _candidate_response(candidate)


@router.get(
    "/v1/borrower-identities/{identity_id}",
    summary="Get a resolved borrower identity",
    response_model=BorrowerIdentityResponse,
    responses={404: {"description": "Identity not found"}},
)
def get_identity(
    identity_id: UUID, user: CurrentUser, workspace: BorrowerIdentityWorkspaceDep
) -> BorrowerIdentityResponse:
    identity = workspace.get_identity(user, identity_id)
    return _identity_response(identity)


@router.get(
    "/v1/borrower-identities/{identity_id}/members",
    summary="List a resolved borrower identity's active party/application links",
    response_model=BorrowerIdentityMemberListResponse,
)
def get_identity_members(
    identity_id: UUID, user: CurrentUser, workspace: BorrowerIdentityWorkspaceDep
) -> BorrowerIdentityMemberListResponse:
    members = workspace.get_members(user, identity_id)
    return BorrowerIdentityMemberListResponse(items=[_member_response(m) for m in members])


@router.get(
    "/v1/borrower-identities/{identity_id}/cross-application-signals",
    summary="Cross-Application Intelligence observations for a resolved borrower identity",
    response_model=CrossApplicationSignalListResponse,
    responses={403: {"description": "Insufficient permissions"}, 404: {"description": "Identity not found"}},
)
def get_cross_application_signals(
    identity_id: UUID,
    user: CurrentUser,
    workspace: CrossApplicationIntelligenceWorkspaceDep,
) -> CrossApplicationSignalListResponse:
    observations = workspace.get_signals(user, identity_id)
    return CrossApplicationSignalListResponse(
        items=[
            CrossApplicationObservationResponse(
                kind=o.kind,
                description=o.description,
                application_ids=list(o.application_ids),
                document_ids=list(o.document_ids),
                finding_ids=list(o.finding_ids),
            )
            for o in observations
        ]
    )
