"""
Enterprise Administration REST endpoints — MIL API v1 (spec 005-enterprise-platform §15).

Endpoints:
    POST   /v1/admin/users                                Create a user
    GET    /v1/admin/users                                List users for the tenant
    GET    /v1/admin/users/{user_id}                       Get a user (with active roles)
    PATCH  /v1/admin/users/{user_id}/deactivate            Deactivate a user
    POST   /v1/admin/users/{user_id}/roles                 Assign a role
    DELETE /v1/admin/users/{user_id}/roles/{role_id}        Revoke a role
    GET    /v1/admin/tenant-config                          List tenant configuration
    PUT    /v1/admin/tenant-config/{config_key}             Set a tenant configuration key
    POST   /v1/admin/api-keys                               Create an API key (raw key shown once)
    GET    /v1/admin/api-keys                               List API keys (metadata only)
    DELETE /v1/admin/api-keys/{api_key_id}                   Revoke an API key

Route handlers are intentionally thin: extract the authenticated user, delegate
to ``IdentityService`` (which enforces ``manage:users``/``manage:roles``
permission and self-escalation prevention itself — routes never check
permissions directly, matching the ``CopilotService`` convention), map the
result to a response schema.

Dependency rule: imports from ``mil.api.deps``, ``mil.api.v1.schemas``,
``mil.identity.models`` (for type annotations only — no repository/service
logic lives here), FastAPI, and the Python standard library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, status

from mil.api.deps import CurrentUser, IdentityServiceDep  # noqa: TC001
from mil.api.v1.schemas import (
    ApiKeyCreatedResponse,
    ApiKeyListResponse,
    ApiKeyResponse,
    AssignRoleRequest,
    CreateApiKeyRequest,
    CreateUserRequest,
    RoleAssignmentResponse,
    TenantConfigurationListResponse,
    TenantConfigurationRequest,
    TenantConfigurationResponse,
    UserListResponse,
    UserResponse,
)

if TYPE_CHECKING:
    from mil.identity.models import User

router = APIRouter(prefix="/v1/admin", tags=["Administration"])


def _user_response(service: IdentityServiceDep, user: CurrentUser, target: User) -> UserResponse:
    roles = service.get_active_role_names(user, target)
    return UserResponse(
        id=target.id,
        tenant_id=target.tenant_id,
        display_name=target.display_name,
        is_active=target.is_active,
        roles=roles,
        created_at=target.created_at,
    )


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@router.post(
    "/users",
    summary="Create a new platform user",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def create_user(
    body: CreateUserRequest,
    user: CurrentUser,
    service: IdentityServiceDep,
) -> UserResponse:
    created = service.create_user(
        user,
        external_identity_id=body.external_identity_id,
        email=body.email,
        display_name=body.display_name,
    )
    return _user_response(service, user, created)


@router.get(
    "/users",
    summary="List platform users for the tenant",
    response_model=UserListResponse,
)
def list_users(user: CurrentUser, service: IdentityServiceDep) -> UserListResponse:
    users = service.list_users(user)
    return UserListResponse(items=[_user_response(service, user, u) for u in users])


@router.get(
    "/users/{user_id}",
    summary="Get a platform user",
    response_model=UserResponse,
    responses={404: {"description": "User not found"}},
)
def get_user(user_id: UUID, user: CurrentUser, service: IdentityServiceDep) -> UserResponse:
    target = service.get_user(user, user_id)
    return _user_response(service, user, target)


@router.patch(
    "/users/{user_id}/deactivate",
    summary="Deactivate a platform user",
    response_model=UserResponse,
    responses={404: {"description": "User not found"}},
)
def deactivate_user(user_id: UUID, user: CurrentUser, service: IdentityServiceDep) -> UserResponse:
    target = service.get_user(user, user_id)
    service.deactivate_user(user, target)
    return _user_response(service, user, target)


# ---------------------------------------------------------------------------
# Role assignment
# ---------------------------------------------------------------------------


@router.post(
    "/users/{user_id}/roles",
    summary="Assign a role to a user",
    response_model=RoleAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Insufficient permissions, or self-escalation attempt"},
        404: {"description": "User not found"},
    },
)
def assign_role(
    user_id: UUID,
    body: AssignRoleRequest,
    user: CurrentUser,
    service: IdentityServiceDep,
) -> RoleAssignmentResponse:
    target = service.get_user(user, user_id)
    assignment = service.assign_role(user, user=target, role_name=body.role_name)
    return RoleAssignmentResponse(
        id=assignment.id,
        user_id=assignment.user_id,
        role_id=assignment.role_id,
        role_name=body.role_name,
        assigned_by=assignment.assigned_by,
        assigned_at=assignment.assigned_at,
        revoked_at=assignment.revoked_at,
    )


@router.delete(
    "/users/{user_id}/roles/{role_id}",
    summary="Revoke a user's role assignment",
    response_model=RoleAssignmentResponse,
    responses={404: {"description": "User or active assignment not found"}},
)
def revoke_role(
    user_id: UUID,
    role_id: UUID,
    user: CurrentUser,
    service: IdentityServiceDep,
) -> RoleAssignmentResponse:
    target = service.get_user(user, user_id)
    assignment = service.revoke_role(user, user=target, role_id=role_id)
    role = service.get_role(user, role_id)
    return RoleAssignmentResponse(
        id=assignment.id,
        user_id=assignment.user_id,
        role_id=assignment.role_id,
        role_name=role.name,
        assigned_by=assignment.assigned_by,
        assigned_at=assignment.assigned_at,
        revoked_at=assignment.revoked_at,
    )


# ---------------------------------------------------------------------------
# Tenant configuration
# ---------------------------------------------------------------------------


@router.get(
    "/tenant-config",
    summary="List tenant configuration entries",
    response_model=TenantConfigurationListResponse,
)
def list_tenant_config(
    user: CurrentUser, service: IdentityServiceDep
) -> TenantConfigurationListResponse:
    configs = service.list_tenant_configuration(user)
    return TenantConfigurationListResponse(
        items=[
            TenantConfigurationResponse(
                id=c.id,
                tenant_id=c.tenant_id,
                config_key=c.config_key,
                config_value=c.config_value,
                updated_by_user_id=c.updated_by_user_id,
                updated_at=c.updated_at,
            )
            for c in configs
        ]
    )


@router.put(
    "/tenant-config/{config_key}",
    summary="Create or update a tenant configuration key",
    response_model=TenantConfigurationResponse,
)
def set_tenant_config(
    config_key: str,
    body: TenantConfigurationRequest,
    user: CurrentUser,
    service: IdentityServiceDep,
) -> TenantConfigurationResponse:
    config = service.set_tenant_configuration(
        user, config_key=config_key, config_value=body.config_value
    )
    return TenantConfigurationResponse(
        id=config.id,
        tenant_id=config.tenant_id,
        config_key=config.config_key,
        config_value=config.config_value,
        updated_by_user_id=config.updated_by_user_id,
        updated_at=config.updated_at,
    )


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------


@router.post(
    "/api-keys",
    summary="Create a scoped, expiring API key",
    description="The raw key value is returned exactly once, in this response. It cannot be retrieved again.",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_api_key(
    body: CreateApiKeyRequest,
    user: CurrentUser,
    service: IdentityServiceDep,
) -> ApiKeyCreatedResponse:
    api_key, raw_key = service.create_api_key(
        user, name=body.name, scopes=body.scopes, ttl_days=body.ttl_days
    )
    return ApiKeyCreatedResponse(
        id=api_key.id,
        tenant_id=api_key.tenant_id,
        name=api_key.name,
        scopes=api_key.scopes,
        expires_at=api_key.expires_at,
        revoked_at=api_key.revoked_at,
        created_by_user_id=api_key.created_by_user_id,
        created_at=api_key.created_at,
        raw_key=raw_key,
    )


@router.get(
    "/api-keys",
    summary="List API keys (metadata only — raw key values are never retrievable)",
    response_model=ApiKeyListResponse,
)
def list_api_keys(user: CurrentUser, service: IdentityServiceDep) -> ApiKeyListResponse:
    keys = service.list_api_keys(user)
    return ApiKeyListResponse(
        items=[
            ApiKeyResponse(
                id=k.id,
                tenant_id=k.tenant_id,
                name=k.name,
                scopes=k.scopes,
                expires_at=k.expires_at,
                revoked_at=k.revoked_at,
                created_by_user_id=k.created_by_user_id,
                created_at=k.created_at,
            )
            for k in keys
        ]
    )


@router.delete(
    "/api-keys/{api_key_id}",
    summary="Revoke an API key",
    response_model=ApiKeyResponse,
    responses={404: {"description": "API key not found"}},
)
def revoke_api_key(
    api_key_id: UUID, user: CurrentUser, service: IdentityServiceDep
) -> ApiKeyResponse:
    api_key = service.get_api_key(user, api_key_id)
    revoked = service.revoke_api_key(user, api_key)
    return ApiKeyResponse(
        id=revoked.id,
        tenant_id=revoked.tenant_id,
        name=revoked.name,
        scopes=revoked.scopes,
        expires_at=revoked.expires_at,
        revoked_at=revoked.revoked_at,
        created_by_user_id=revoked.created_by_user_id,
        created_at=revoked.created_at,
    )
