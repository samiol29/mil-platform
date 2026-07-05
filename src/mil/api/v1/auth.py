"""
Authentication endpoints — MIL API v1.

Endpoints:
    GET /v1/me — Return the authenticated caller's identity claims.

System/operational probes (``/v1/health``, ``/v1/ready``, ``/v1/live``,
``/v1/metrics``) live in ``mil.api.v1.ops`` (Sprint 8 — Production
Hardening).

Dependency rule: imports from ``mil.api.deps``, ``mil.api.v1.schemas``, and
FastAPI only.  No business service is called.
"""

from __future__ import annotations

from fastapi import APIRouter

from mil.api.deps import CurrentUser  # noqa: TC001
from mil.api.v1.schemas import CurrentUserResponse

router = APIRouter(tags=["System"])


@router.get(
    "/v1/me",
    summary="Current authenticated user",
    description=(
        "Return the identity claims of the authenticated caller. "
        "Useful for clients to verify token validity and inspect role assignments."
    ),
    response_model=CurrentUserResponse,
    responses={
        401: {"description": "Authentication required"},
    },
)
def get_me(user: CurrentUser) -> CurrentUserResponse:
    """Return the authenticated caller's identity."""
    return CurrentUserResponse(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        roles=sorted(user.roles),
        email=user.email,
        display_name=user.display_name,
    )
