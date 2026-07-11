"""
Policy Engine + Policy Administration REST endpoints — MIL API v1
(spec 005-enterprise-platform §3/§4).

Endpoints:
    GET    /v1/policy-packs                                  List packs for the tenant
    POST   /v1/policy-packs                                  Create a draft pack
    GET    /v1/policy-packs/{pack_id}                          Get a pack + its rules
    POST   /v1/policy-packs/{pack_id}/rules                   Add a rule to a draft pack
    POST   /v1/policy-packs/{pack_id}/submit-for-approval      Submit for maker-checker approval
    GET    /v1/policy-packs/{pack_id}/approvals                List approval history
    POST   /v1/policy-pack-approvals/{approval_id}/approve     Approve a pending request
    POST   /v1/policy-pack-approvals/{approval_id}/reject      Reject a pending request (reason required)
    POST   /v1/policy-packs/{pack_id}/activate                 Activate (requires an approved request)
    GET    /v1/applications/{application_id}/policy-results    List Policy results for an application

Route handlers are thin. `PolicyService`'s new maker-checker/read methods
(`submit_for_approval`, `approve_pack`, `reject_pack`,
`activate_pack_if_approved`, `get_pack`, `get_packs_for_tenant`,
`get_rules_for_pack`, `get_results_for_application`, `get_approvals_for_pack`)
self-check permissions exactly like `CopilotService`/`IdentityService`. The
pre-existing `create_pack`/`add_rule`/`activate_pack`/`deactivate_pack`
methods do NOT self-check (unchanged from before this module, to avoid
breaking their existing callers/tests) — this route layer calls
`require_permission` directly before invoking those specific methods, the
one deliberate exception to "the service always checks" documented in
`policy/service.py`'s own module docstring.

Dependency rule: imports from `mil.api.deps`, `mil.api.v1.schemas`,
`mil.policy.models` (type annotations only), FastAPI, and the Python
standard library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, status

from mil.api.deps import CurrentUser, PolicyServiceDep  # noqa: TC001
from mil.api.v1.schemas import (
    AddPolicyRuleRequest,
    CreatePolicyPackRequest,
    PolicyPackApprovalListResponse,
    PolicyPackApprovalResponse,
    PolicyPackListResponse,
    PolicyPackResponse,
    PolicyResultListResponse,
    PolicyResultResponse,
    PolicyRuleResponse,
    RejectPolicyPackRequest,
)
from mil.kernel.security import Permission, require_permission

if TYPE_CHECKING:
    from mil.policy.models import PolicyPack, PolicyPackApproval, PolicyResult, PolicyRule

router = APIRouter(prefix="/v1/policy-packs", tags=["Policy"])
approvals_router = APIRouter(prefix="/v1/policy-pack-approvals", tags=["Policy"])
application_policy_router = APIRouter(
    prefix="/v1/applications/{application_id}/policy-results", tags=["Policy"]
)


def _pack_response(pack: PolicyPack) -> PolicyPackResponse:
    return PolicyPackResponse(
        id=pack.id,
        tenant_id=pack.tenant_id,
        version=pack.version,
        name=pack.name,
        jurisdiction=pack.jurisdiction,
        is_active=pack.is_active,
        activated_at=pack.activated_at,
        deactivated_at=pack.deactivated_at,
        created_at=pack.created_at,
    )


def _rule_response(rule: PolicyRule) -> PolicyRuleResponse:
    return PolicyRuleResponse(
        id=rule.id,
        policy_pack_id=rule.policy_pack_id,
        rule_key=rule.rule_key,
        name=rule.name,
        description=rule.description,
        severity=rule.severity,
        created_at=rule.created_at,
    )


def _approval_response(approval: PolicyPackApproval) -> PolicyPackApprovalResponse:
    return PolicyPackApprovalResponse(
        id=approval.id,
        policy_pack_id=approval.policy_pack_id,
        requested_by_user_id=approval.requested_by_user_id,
        decided_by_user_id=approval.decided_by_user_id,
        decision=approval.decision,
        reason=approval.reason,
        decided_at=approval.decided_at,
        created_at=approval.created_at,
    )


def _result_response(result: PolicyResult) -> PolicyResultResponse:
    return PolicyResultResponse(
        id=result.id,
        finding_id=result.finding_id,
        application_id=result.application_id,
        policy_pack_id=result.policy_pack_id,
        policy_version=result.policy_version,
        outcome=result.outcome,
        triggered_rule_keys=result.triggered_rule_keys,
        evaluated_rule_keys=result.evaluated_rule_keys,
        passed_rule_keys=result.passed_rule_keys,
        evaluated_at=result.evaluated_at,
        created_at=result.created_at,
    )


# ---------------------------------------------------------------------------
# Policy Packs
# ---------------------------------------------------------------------------


@router.get("", summary="List Policy Packs for the tenant", response_model=PolicyPackListResponse)
def list_policy_packs(user: CurrentUser, service: PolicyServiceDep) -> PolicyPackListResponse:
    packs = service.get_packs_for_tenant(user)
    return PolicyPackListResponse(items=[_pack_response(p) for p in packs])


@router.post(
    "",
    summary="Create a draft Policy Pack",
    response_model=PolicyPackResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_policy_pack(
    body: CreatePolicyPackRequest, user: CurrentUser, service: PolicyServiceDep
) -> PolicyPackResponse:
    require_permission(user, Permission.DRAFT_POLICY_PACK)
    pack = service.create_pack(
        tenant_id=user.tenant_id,
        version=body.version,
        name=body.name,
        content_hash=body.content_hash,
        jurisdiction=body.jurisdiction,
        created_by=user.user_id,
    )
    return _pack_response(pack)


@router.get(
    "/{pack_id}",
    summary="Get a Policy Pack and its rule catalogue",
    response_model=PolicyPackResponse,
)
def get_policy_pack(pack_id: UUID, user: CurrentUser, service: PolicyServiceDep) -> PolicyPackResponse:
    return _pack_response(service.get_pack(user, pack_id))


@router.get(
    "/{pack_id}/rules",
    summary="List rules for a Policy Pack",
    response_model=list[PolicyRuleResponse],
)
def list_policy_rules(
    pack_id: UUID, user: CurrentUser, service: PolicyServiceDep
) -> list[PolicyRuleResponse]:
    rules = service.get_rules_for_pack(user, pack_id)
    return [_rule_response(r) for r in rules]


@router.post(
    "/{pack_id}/rules",
    summary="Add a rule to a draft Policy Pack",
    response_model=PolicyRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_policy_rule(
    pack_id: UUID,
    body: AddPolicyRuleRequest,
    user: CurrentUser,
    service: PolicyServiceDep,
) -> PolicyRuleResponse:
    require_permission(user, Permission.DRAFT_POLICY_PACK)
    rule = service.add_rule(
        policy_pack_id=pack_id,
        tenant_id=user.tenant_id,
        rule_key=body.rule_key,
        name=body.name,
        description=body.description,
        severity=body.severity,
    )
    return _rule_response(rule)


# ---------------------------------------------------------------------------
# Maker-checker approval workflow
# ---------------------------------------------------------------------------


@router.post(
    "/{pack_id}/submit-for-approval",
    summary="Submit a draft Policy Pack for maker-checker approval",
    response_model=PolicyPackApprovalResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_for_approval(
    pack_id: UUID, user: CurrentUser, service: PolicyServiceDep
) -> PolicyPackApprovalResponse:
    pack = service.get_pack(user, pack_id)
    approval = service.submit_for_approval(user, pack)
    return _approval_response(approval)


@router.get(
    "/{pack_id}/approvals",
    summary="List the approval history for a Policy Pack",
    response_model=PolicyPackApprovalListResponse,
)
def list_approvals(
    pack_id: UUID, user: CurrentUser, service: PolicyServiceDep
) -> PolicyPackApprovalListResponse:
    approvals = service.get_approvals_for_pack(user, pack_id)
    return PolicyPackApprovalListResponse(items=[_approval_response(a) for a in approvals])


@router.post(
    "/{pack_id}/activate",
    summary="Activate a Policy Pack (requires an approved request)",
    response_model=PolicyPackResponse,
    responses={404: {"description": "No approved request exists for this pack"}},
)
def activate_policy_pack(
    pack_id: UUID, user: CurrentUser, service: PolicyServiceDep
) -> PolicyPackResponse:
    pack = service.get_pack(user, pack_id)
    activated = service.activate_pack_if_approved(user, pack)
    return _pack_response(activated)


@approvals_router.post(
    "/{approval_id}/approve",
    summary="Approve a pending Policy Pack submission",
    response_model=PolicyPackApprovalResponse,
)
def approve_policy_pack(
    approval_id: UUID, user: CurrentUser, service: PolicyServiceDep
) -> PolicyPackApprovalResponse:
    approval = service.get_approval(user, approval_id)
    decided = service.approve_pack(user, approval, tenant_id=user.tenant_id)
    return _approval_response(decided)


@approvals_router.post(
    "/{approval_id}/reject",
    summary="Reject a pending Policy Pack submission",
    response_model=PolicyPackApprovalResponse,
)
def reject_policy_pack(
    approval_id: UUID,
    body: RejectPolicyPackRequest,
    user: CurrentUser,
    service: PolicyServiceDep,
) -> PolicyPackApprovalResponse:
    approval = service.get_approval(user, approval_id)
    decided = service.reject_pack(user, approval, tenant_id=user.tenant_id, reason=body.reason)
    return _approval_response(decided)


# ---------------------------------------------------------------------------
# Policy results (application-scoped read)
# ---------------------------------------------------------------------------


@application_policy_router.get(
    "",
    summary="List Policy results for an application",
    response_model=PolicyResultListResponse,
)
def list_policy_results(
    application_id: UUID, user: CurrentUser, service: PolicyServiceDep
) -> PolicyResultListResponse:
    results = service.get_results_for_application(user, application_id)
    return PolicyResultListResponse(items=[_result_response(r) for r in results])
