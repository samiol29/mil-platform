"""
Security & Compliance REST endpoints — MIL API v1 (spec 005-enterprise-
platform §16, Wave 4).

Endpoints:
    GET /v1/compliance/retention-policies   List a tenant's retention policies
    PUT /v1/compliance/retention-policies   Set (create/update) a retention policy
    GET /v1/compliance/access-log           Access-log report for an application

Route handlers are thin; `ComplianceWorkspace`'s methods self-check
`manage:compliance`/`read:compliance`.

Dependency rule: imports from `mil.api.deps`, `mil.api.v1.schemas`, FastAPI,
and the Python standard library only.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from uuid import UUID  # noqa: TC003

from fastapi import APIRouter

from mil.api.deps import ComplianceWorkspaceDep, CurrentUser  # noqa: TC001
from mil.api.v1.schemas import (
    AccessLogEntryResponse,
    AccessLogResponse,
    RetentionPolicyListResponse,
    RetentionPolicyResponse,
    SetRetentionPolicyRequest,
)

router = APIRouter(prefix="/v1/compliance", tags=["Compliance"])


def _policy_response(policy: object) -> RetentionPolicyResponse:
    return RetentionPolicyResponse(
        id=policy.id,  # type: ignore[attr-defined]
        tenant_id=policy.tenant_id,  # type: ignore[attr-defined]
        data_category=policy.data_category,  # type: ignore[attr-defined]
        retention_period_days=policy.retention_period_days,  # type: ignore[attr-defined]
        action=policy.action,  # type: ignore[attr-defined]
    )


@router.get(
    "/retention-policies",
    summary="List this tenant's data retention policies",
    response_model=RetentionPolicyListResponse,
    responses={403: {"description": "Insufficient permissions"}},
)
def list_retention_policies(
    user: CurrentUser, workspace: ComplianceWorkspaceDep
) -> RetentionPolicyListResponse:
    policies = workspace.get_retention_policies(user)
    return RetentionPolicyListResponse(items=[_policy_response(p) for p in policies])


@router.put(
    "/retention-policies",
    summary="Set (create or update) a data retention policy",
    response_model=RetentionPolicyResponse,
    responses={
        403: {"description": "Insufficient permissions"},
        422: {"description": "DELETE is not permitted for AUDIT_EVENT/EVIDENCE categories"},
    },
)
def set_retention_policy(
    body: SetRetentionPolicyRequest, user: CurrentUser, workspace: ComplianceWorkspaceDep
) -> RetentionPolicyResponse:
    policy = workspace.set_retention_policy(
        user,
        data_category=body.data_category,
        retention_period_days=body.retention_period_days,
        action=body.action,
    )
    return _policy_response(policy)


@router.get(
    "/access-log",
    summary="Compliance access-log report for an application over a date range",
    response_model=AccessLogResponse,
    responses={403: {"description": "Insufficient permissions"}},
)
def get_access_log(
    application_id: UUID,
    from_date: datetime,
    to_date: datetime,
    user: CurrentUser,
    workspace: ComplianceWorkspaceDep,
) -> AccessLogResponse:
    entries = workspace.get_access_log(
        user, application_id=application_id, from_date=from_date, to_date=to_date
    )
    return AccessLogResponse(
        application_id=application_id,
        from_date=from_date,
        to_date=to_date,
        items=[
            AccessLogEntryResponse(
                event_type=e.event_type,
                actor_id=e.actor_id,
                actor_type=e.actor_type,
                occurred_at=e.occurred_at,
            )
            for e in entries
        ],
    )
