"""
Persistence gateway for the Identity & Access bounded context.

``IdentityRepository`` covers ``User``, ``Role``, and ``RoleAssignment`` (all
already defined in ``mil.identity.models`` and migrated to ``core.users`` /
``core.roles`` / ``core.role_assignments`` since migration 0001), plus the two
new administration entities this module adds: ``TenantConfiguration`` and
``ApiKey``.

Mirrors the structure of ``mil.policy.repository.PolicyRepository`` — plain
CRUD/query methods, no business logic. Does not commit; the caller's Unit of
Work (the FastAPI request session, via ``AdminService``) owns the transaction.

Dependency rule: imports only from ``mil.identity.models`` and the Python
standard library plus SQLAlchemy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from mil.identity.models import ApiKey, Role, RoleAssignment, TenantConfiguration, User

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session


class IdentityRepository:
    """Persistence gateway for Identity & Administration entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # User
    # ------------------------------------------------------------------

    def save_user(self, user: User) -> None:
        self._session.add(user)
        self._session.flush()

    def get_user_by_id(self, user_id: UUID) -> User | None:
        return self._session.get(User, user_id)

    def get_user_by_external_identity(
        self, tenant_id: UUID, external_identity_id: str
    ) -> User | None:
        stmt = select(User).where(
            User.tenant_id == tenant_id,
            User.external_identity_id == external_identity_id,
        )
        return self._session.scalars(stmt).one_or_none()

    def list_users_for_tenant(self, tenant_id: UUID) -> list[User]:
        stmt = select(User).where(User.tenant_id == tenant_id).order_by(User.created_at.desc())
        return list(self._session.scalars(stmt))

    # ------------------------------------------------------------------
    # Role
    # ------------------------------------------------------------------

    def save_role(self, role: Role) -> None:
        self._session.add(role)
        self._session.flush()

    def get_role_by_id(self, role_id: UUID) -> Role | None:
        return self._session.get(Role, role_id)

    def get_role_by_name(self, tenant_id: UUID, name: str) -> Role | None:
        stmt = select(Role).where(Role.tenant_id == tenant_id, Role.name == name)
        return self._session.scalars(stmt).one_or_none()

    def list_roles_for_tenant(self, tenant_id: UUID) -> list[Role]:
        stmt = select(Role).where(Role.tenant_id == tenant_id).order_by(Role.name)
        return list(self._session.scalars(stmt))

    # ------------------------------------------------------------------
    # RoleAssignment
    # ------------------------------------------------------------------

    def save_role_assignment(self, assignment: RoleAssignment) -> None:
        self._session.add(assignment)
        self._session.flush()

    def get_active_assignments_for_user(self, user_id: UUID) -> list[RoleAssignment]:
        stmt = select(RoleAssignment).where(
            RoleAssignment.user_id == user_id,
            RoleAssignment.revoked_at.is_(None),
        )
        return list(self._session.scalars(stmt))

    def get_active_assignment(self, user_id: UUID, role_id: UUID) -> RoleAssignment | None:
        stmt = select(RoleAssignment).where(
            RoleAssignment.user_id == user_id,
            RoleAssignment.role_id == role_id,
            RoleAssignment.revoked_at.is_(None),
        )
        return self._session.scalars(stmt).one_or_none()

    # ------------------------------------------------------------------
    # TenantConfiguration
    # ------------------------------------------------------------------

    def save_tenant_configuration(self, config: TenantConfiguration) -> None:
        self._session.add(config)
        self._session.flush()

    def get_tenant_configuration(
        self, tenant_id: UUID, config_key: str
    ) -> TenantConfiguration | None:
        stmt = select(TenantConfiguration).where(
            TenantConfiguration.tenant_id == tenant_id,
            TenantConfiguration.config_key == config_key,
        )
        return self._session.scalars(stmt).one_or_none()

    def list_tenant_configuration(self, tenant_id: UUID) -> list[TenantConfiguration]:
        stmt = select(TenantConfiguration).where(TenantConfiguration.tenant_id == tenant_id)
        return list(self._session.scalars(stmt))

    # ------------------------------------------------------------------
    # ApiKey
    # ------------------------------------------------------------------

    def save_api_key(self, api_key: ApiKey) -> None:
        self._session.add(api_key)
        self._session.flush()

    def get_api_key_by_id(self, api_key_id: UUID) -> ApiKey | None:
        return self._session.get(ApiKey, api_key_id)

    def get_api_key_by_hash(self, hashed_key: str) -> ApiKey | None:
        stmt = select(ApiKey).where(ApiKey.hashed_key == hashed_key)
        return self._session.scalars(stmt).one_or_none()

    def list_api_keys_for_tenant(self, tenant_id: UUID) -> list[ApiKey]:
        stmt = (
            select(ApiKey).where(ApiKey.tenant_id == tenant_id).order_by(ApiKey.created_at.desc())
        )
        return list(self._session.scalars(stmt))
