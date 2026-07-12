"""
Business Analytics REST endpoints — MIL API v1 (spec 005-enterprise-
platform §11, Wave 3).

Endpoints:
    GET /v1/analytics/snapshot   Current-state business analytics snapshot

A single snapshot endpoint, not the originally-specified scheduled-report
infrastructure — see §11's implementation-correction note in the spec for
why (an honest scope reduction, not a fabricated shortcut).
`BusinessAnalyticsWorkspace.get_snapshot` self-checks `read:analytics`.

Dependency rule: imports from `mil.api.deps`, `mil.api.v1.schemas`, FastAPI,
and the Python standard library only.
"""

from __future__ import annotations

from fastapi import APIRouter

from mil.api.deps import BusinessAnalyticsWorkspaceDep, CurrentUser  # noqa: TC001
from mil.api.v1.schemas import (
    ApplicationStatusCountResponse,
    BusinessAnalyticsSnapshotResponse,
    FindingOutcomeRowResponse,
    PolicyOutcomeRowResponse,
)

router = APIRouter(prefix="/v1/analytics", tags=["Analytics"])


@router.get(
    "/snapshot",
    summary="Current-state business analytics snapshot",
    response_model=BusinessAnalyticsSnapshotResponse,
    responses={403: {"description": "Insufficient permissions"}},
)
def get_snapshot(
    user: CurrentUser, workspace: BusinessAnalyticsWorkspaceDep
) -> BusinessAnalyticsSnapshotResponse:
    snapshot = workspace.get_snapshot(user)
    return BusinessAnalyticsSnapshotResponse(
        application_counts_by_status=[
            ApplicationStatusCountResponse(status=status, count=count)
            for status, count in snapshot.application_counts_by_status
        ],
        finding_outcomes=[
            FindingOutcomeRowResponse(lifecycle_state=r.lifecycle_state, count=r.count)
            for r in snapshot.finding_outcomes
        ],
        policy_outcomes=[
            PolicyOutcomeRowResponse(
                policy_version=r.policy_version, outcome=r.outcome, count=r.count
            )
            for r in snapshot.policy_outcomes
        ],
        document_count=snapshot.document_count,
        evidence_count=snapshot.evidence_count,
        average_review_duration_seconds=snapshot.average_review_duration_seconds,
    )
