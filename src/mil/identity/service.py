"""
IdentityService — use-case orchestrator for the Identity & Access bounded
context (Enterprise Administration, spec §15).

Mirrors ``mil.policy.service.PolicyService``'s shape: one service per unit of
work, wired to a repository and an ``AuditWriter`` sharing the caller's
session, so every write and its audit event commit atomically.

Responsibilities:

1. **User lifecycle** — create/deactivate platform users.
2. **Role assignment** — assign/revoke a Role to/from a User, enforcing
   self-escalation prevention (FR-ADMIN-005): a user may never grant a role
   to themselves through this service.
3. **Tenant configuration** — get/set arbitrary tenant-scoped key/value
   configuration (LOS connections list, notification provider config, etc.
   consumed by later waves).
4. **API keys** — create (returns the raw key exactly once) / revoke scoped,
   expiring service-to-service credentials.

Every mutating operation emits an immutable Audit Event (Principle VIII),
matching the discipline already established in ``PolicyService``.

Dependency rule: imports only from ``mil.identity``, ``mil.kernel``, and the
Python standard library. No other bounded context is imported.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from mil.identity.models import ApiKey, Role, RoleAssignment, TenantConfiguration, User
from mil.kernel.errors import AuthorizationError, NotFoundError, ValidationError
from mil.kernel.security import Permission, require_permission

if TYPE_CHECKING:
    from uuid import UUID

    from mil.audit.writer import AuditWriter
    from mil.identity.repository import IdentityRepository
    from mil.kernel.security import AuthenticatedUser


def _hash_email(email: str) -> str:
    """SHA-256 hash of a normalized email — never store plaintext PII (Principle V)."""
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def _generate_api_key() -> tuple[str, str]:
    """Return ``(raw_key, hashed_key)``. The raw key is shown to the caller once."""
    raw = f"mil_{secrets.token_urlsafe(32)}"
    hashed = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, hashed


class IdentityService:
    """
    Orchestrates user/role/tenant-configuration/API-key administration.

    Every method takes ``caller`` (the authenticated principal, from
    ``mil.api.deps.CurrentUser``) as its first argument and calls
    ``require_permission`` as its first action — mirroring
    ``CopilotService``'s documented convention: routes never check
    permissions directly, the service always does.
    """

    def __init__(self, repository: IdentityRepository, audit: AuditWriter) -> None:
        self._repo = repository
        self._audit = audit

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def create_user(
        self,
        caller: AuthenticatedUser,
        *,
        external_identity_id: str,
        email: str,
        display_name: str,
    ) -> User:
        """Create a new platform user and record ``USER_CREATED``."""
        require_permission(caller, Permission.MANAGE_USERS)
        user = User.create(
            tenant_id=caller.tenant_id,
            external_identity_id=external_identity_id,
            email_hash=_hash_email(email),
            display_name=display_name,
        )
        self._repo.save_user(user)
        self._audit.record(
            event_type="USER_CREATED",
            entity_type="USER",
            entity_id=user.id,
            tenant_id=caller.tenant_id,
            actor_id=caller.user_id,
            event_data={"display_name": user.display_name},
        )
        return user

    def deactivate_user(self, caller: AuthenticatedUser, user: User) -> User:
        """Deactivate a user and record ``USER_DEACTIVATED``."""
        require_permission(caller, Permission.MANAGE_USERS)
        user.deactivate()
        self._repo.save_user(user)
        self._audit.record(
            event_type="USER_DEACTIVATED",
            entity_type="USER",
            entity_id=user.id,
            tenant_id=user.tenant_id,
            actor_id=caller.user_id,
            event_data={},
        )
        return user

    def list_users(self, caller: AuthenticatedUser) -> list[User]:
        require_permission(caller, Permission.MANAGE_USERS)
        return self._repo.list_users_for_tenant(caller.tenant_id)

    def get_user(self, caller: AuthenticatedUser, user_id: UUID) -> User:
        require_permission(caller, Permission.MANAGE_USERS)
        user = self._repo.get_user_by_id(user_id)
        if user is None or user.tenant_id != caller.tenant_id:
            raise NotFoundError("User", user_id)
        return user

    # ------------------------------------------------------------------
    # Roles / Role assignment
    # ------------------------------------------------------------------

    def get_or_create_role(self, *, tenant_id: UUID, name: str) -> Role:
        """
        Return the tenant's Role record for ``name``, creating it on first
        use. Roles are catalogue data — the platform's fixed set of role
        *names* lives in ``mil.kernel.security.Role``; this just materializes
        a per-tenant row the first time a role is actually assigned. Not
        permission-gated on its own — always called from within
        ``assign_role``, which is.
        """
        existing = self._repo.get_role_by_name(tenant_id, name)
        if existing is not None:
            return existing
        role = Role.create(tenant_id=tenant_id, name=name)
        self._repo.save_role(role)
        return role

    def assign_role(
        self,
        caller: AuthenticatedUser,
        *,
        user: User,
        role_name: str,
    ) -> RoleAssignment:
        """
        Assign a role to a user.

        Raises:
            AuthorizationError: If ``caller.user_id == user.id`` — self-
                escalation is never permitted through this service
                (FR-ADMIN-005), regardless of the caller's own permissions.
        """
        require_permission(caller, Permission.MANAGE_ROLES)
        if caller.user_id == user.id:
            raise AuthorizationError(
                "A user may not assign a role to themselves (self-escalation prevention)."
            )
        role = self.get_or_create_role(tenant_id=user.tenant_id, name=role_name)
        existing = self._repo.get_active_assignment(user.id, role.id)
        if existing is not None:
            return existing
        assignment = RoleAssignment.create(
            user_id=user.id, role_id=role.id, assigned_by=caller.user_id
        )
        self._repo.save_role_assignment(assignment)
        self._audit.record(
            event_type="ROLE_ASSIGNED",
            entity_type="ROLE_ASSIGNMENT",
            entity_id=assignment.id,
            tenant_id=user.tenant_id,
            actor_id=caller.user_id,
            event_data={"user_id": str(user.id), "role_name": role_name},
        )
        return assignment

    def revoke_role(
        self,
        caller: AuthenticatedUser,
        *,
        user: User,
        role_id: UUID,
    ) -> RoleAssignment:
        """Revoke a user's active assignment of the given role."""
        require_permission(caller, Permission.MANAGE_ROLES)
        assignment = self._repo.get_active_assignment(user.id, role_id)
        if assignment is None:
            raise NotFoundError("RoleAssignment", f"user={user.id} role={role_id}")
        assignment.revoke()
        self._repo.save_role_assignment(assignment)
        self._audit.record(
            event_type="ROLE_REVOKED",
            entity_type="ROLE_ASSIGNMENT",
            entity_id=assignment.id,
            tenant_id=user.tenant_id,
            actor_id=caller.user_id,
            event_data={"user_id": str(user.id), "role_id": str(role_id)},
        )
        return assignment

    def get_active_role_names(self, caller: AuthenticatedUser, user: User) -> list[str]:
        require_permission(caller, Permission.MANAGE_USERS)
        assignments = self._repo.get_active_assignments_for_user(user.id)
        roles = [self._repo.get_role_by_id(a.role_id) for a in assignments]
        return [r.name for r in roles if r is not None]

    def get_role(self, caller: AuthenticatedUser, role_id: UUID) -> Role:
        require_permission(caller, Permission.MANAGE_ROLES)
        role = self._repo.get_role_by_id(role_id)
        if role is None or role.tenant_id != caller.tenant_id:
            raise NotFoundError("Role", role_id)
        return role

    # ------------------------------------------------------------------
    # Tenant configuration
    # ------------------------------------------------------------------

    def list_tenant_configuration(self, caller: AuthenticatedUser) -> list[TenantConfiguration]:
        require_permission(caller, Permission.MANAGE_USERS)
        return self._repo.list_tenant_configuration(caller.tenant_id)

    def set_tenant_configuration(
        self,
        caller: AuthenticatedUser,
        *,
        config_key: str,
        config_value: dict[str, object],
    ) -> TenantConfiguration:
        """Create or update a tenant configuration key and record the change."""
        require_permission(caller, Permission.MANAGE_USERS)
        existing = self._repo.get_tenant_configuration(caller.tenant_id, config_key)
        if existing is not None:
            existing.update_value(config_value, caller.user_id)
            self._repo.save_tenant_configuration(existing)
            config = existing
            event_type = "TENANT_CONFIG_UPDATED"
        else:
            config = TenantConfiguration.create(
                tenant_id=caller.tenant_id,
                config_key=config_key,
                config_value=config_value,
                updated_by_user_id=caller.user_id,
            )
            self._repo.save_tenant_configuration(config)
            event_type = "TENANT_CONFIG_CREATED"
        self._audit.record(
            event_type=event_type,
            entity_type="TENANT_CONFIGURATION",
            entity_id=config.id,
            tenant_id=caller.tenant_id,
            actor_id=caller.user_id,
            event_data={"config_key": config_key},
        )
        return config

    # ------------------------------------------------------------------
    # API keys
    # ------------------------------------------------------------------

    def create_api_key(
        self,
        caller: AuthenticatedUser,
        *,
        name: str,
        scopes: list[str],
        ttl_days: int,
    ) -> tuple[ApiKey, str]:
        """
        Create a new API key.

        Returns ``(ApiKey, raw_key)`` — the raw key is never retrievable again
        after this call returns; the caller must display it exactly once.
        """
        require_permission(caller, Permission.MANAGE_USERS)
        if ttl_days <= 0:
            raise ValidationError("ttl_days must be positive", field="ttl_days")
        raw_key, hashed_key = _generate_api_key()
        expires_at = datetime.now(UTC) + timedelta(days=ttl_days)
        api_key = ApiKey.create(
            tenant_id=caller.tenant_id,
            name=name,
            hashed_key=hashed_key,
            scopes=scopes,
            expires_at=expires_at,
            created_by_user_id=caller.user_id,
        )
        self._repo.save_api_key(api_key)
        self._audit.record(
            event_type="API_KEY_CREATED",
            entity_type="API_KEY",
            entity_id=api_key.id,
            tenant_id=caller.tenant_id,
            actor_id=caller.user_id,
            event_data={"name": name, "scopes": scopes, "expires_at": expires_at.isoformat()},
        )
        return api_key, raw_key

    def get_api_key(self, caller: AuthenticatedUser, api_key_id: UUID) -> ApiKey:
        require_permission(caller, Permission.MANAGE_USERS)
        api_key = self._repo.get_api_key_by_id(api_key_id)
        if api_key is None or api_key.tenant_id != caller.tenant_id:
            raise NotFoundError("ApiKey", api_key_id)
        return api_key

    def revoke_api_key(self, caller: AuthenticatedUser, api_key: ApiKey) -> ApiKey:
        require_permission(caller, Permission.MANAGE_USERS)
        api_key.revoke()
        self._repo.save_api_key(api_key)
        self._audit.record(
            event_type="API_KEY_REVOKED",
            entity_type="API_KEY",
            entity_id=api_key.id,
            tenant_id=api_key.tenant_id,
            actor_id=caller.user_id,
            event_data={"name": api_key.name},
        )
        return api_key

    def list_api_keys(self, caller: AuthenticatedUser) -> list[ApiKey]:
        require_permission(caller, Permission.MANAGE_USERS)
        return self._repo.list_api_keys_for_tenant(caller.tenant_id)
