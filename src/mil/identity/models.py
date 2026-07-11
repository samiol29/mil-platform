"""
ORM models for the Identity & Access bounded context.

This module defines the SQLAlchemy models for ``core.users``,
``core.roles``, and ``core.role_assignments``.

Schema: all tables live in the ``core`` PostgreSQL schema.

Dependency rule: this module imports from ``mil.kernel.db`` and the
Python standard library only.  No bounded context may import from
another bounded context.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mil.kernel.db import Base
from mil.kernel.errors import ValidationError

# ---------------------------------------------------------------------------
# ORM Model: User
# ---------------------------------------------------------------------------


class User(Base):
    """
    Represents an authenticated platform user.

    ``external_identity_id`` is the ``sub`` claim from the external IdP
    token.  It is the stable, IdP-assigned identifier for the user.

    ``email_hash`` stores a hashed form of the email address to support
    lookup by email without storing PII in plaintext.  The hash is
    computed by the identity bounded context using SHA-256.

    PII is not stored in plaintext per Engineering Constitution Principle V
    (Security & Privacy by Design).
    """

    __tablename__ = "users"
    __table_args__ = {"schema": "core"}

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    external_identity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    role_assignments: Mapped[list[RoleAssignment]] = relationship(
        "RoleAssignment",
        foreign_keys="RoleAssignment.user_id",
        back_populates="user",
        lazy="select",
    )

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        external_identity_id: str,
        email_hash: str,
        display_name: str,
    ) -> User:
        """
        Create a new platform user (Enterprise Administration, spec §15).

        The caller (``IdentityService``) is responsible for computing
        ``email_hash`` (SHA-256 of the real email — Principle V, no plaintext
        PII) before calling this factory.
        """
        if not external_identity_id or not external_identity_id.strip():
            raise ValidationError(
                "external_identity_id must not be empty", field="external_identity_id"
            )
        if not display_name or not display_name.strip():
            raise ValidationError("display_name must not be empty", field="display_name")
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            external_identity_id=external_identity_id.strip(),
            email_hash=email_hash,
            display_name=display_name.strip(),
            is_active=True,
            created_at=datetime.now(UTC),
        )

    def deactivate(self) -> None:
        """Deactivate this user. Idempotent — deactivating twice is a no-op."""
        self.is_active = False

    def __repr__(self) -> str:
        return f"<User id={self.id} tenant={self.tenant_id}>"


# ---------------------------------------------------------------------------
# ORM Model: Role
# ---------------------------------------------------------------------------


class Role(Base):
    """
    An RBAC role that can be assigned to users.

    Role names match the string constants in ``mil.kernel.security.Role``
    (e.g. ``"VERIFICATION_OFFICER"``, ``"UNDERWRITER"``).  The name is
    the stable identifier used throughout the platform; the ``id`` is an
    internal surrogate key.

    Roles are tenant-scoped — each tenant maintains its own role records
    even if the names match the platform defaults.
    """

    __tablename__ = "roles"
    __table_args__ = {"schema": "core"}

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    role_assignments: Mapped[list[RoleAssignment]] = relationship(
        "RoleAssignment",
        back_populates="role",
        lazy="select",
    )

    @classmethod
    def create(
        cls, *, tenant_id: UUID, name: str, description: str | None = None
    ) -> Role:
        """
        Create a tenant-scoped Role record.

        ``name`` should match one of the string constants in
        ``mil.kernel.security.Role`` (e.g. ``"UNDERWRITER"``) — this class
        does not enforce that against the kernel constants (no bounded
        context may import another), so ``IdentityService`` validates it.
        """
        if not name or not name.strip():
            raise ValidationError("name must not be empty", field="name")
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            name=name.strip(),
            description=description,
            created_at=datetime.now(UTC),
        )

    def __repr__(self) -> str:
        return f"<Role name={self.name!r} tenant={self.tenant_id}>"


# ---------------------------------------------------------------------------
# ORM Model: RoleAssignment
# ---------------------------------------------------------------------------


class RoleAssignment(Base):
    """
    An assignment of a Role to a User, with optional revocation.

    An assignment is active when ``revoked_at`` is NULL.  Revocation uses
    a soft-delete (setting ``revoked_at``) rather than row deletion to
    preserve the audit history of who held which roles and when.

    Every assignment records the ``assigned_by`` user to satisfy the
    Engineering Constitution Principle VIII (Auditability) requirement
    that all significant platform actions be traceable.
    """

    __tablename__ = "role_assignments"
    __table_args__ = {"schema": "core"}

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.users.id"),
        nullable=False,
    )
    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.roles.id"),
        nullable=False,
    )
    assigned_by: Mapped[UUID] = mapped_column(
        ForeignKey("core.users.id"),
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    # NULL = still active; non-NULL = revoked at this timestamp.
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped[User] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="role_assignments",
    )
    role: Mapped[Role] = relationship(
        "Role",
        back_populates="role_assignments",
    )

    @classmethod
    def create(cls, *, user_id: UUID, role_id: UUID, assigned_by: UUID) -> RoleAssignment:
        """Create a new, active Role Assignment."""
        return cls(
            id=uuid4(),
            user_id=user_id,
            role_id=role_id,
            assigned_by=assigned_by,
            assigned_at=datetime.now(UTC),
            revoked_at=None,
        )

    def revoke(self) -> None:
        """
        Revoke this assignment (soft-delete — Principle VIII, preserve
        history of who held which roles and when).

        Raises:
            ValidationError: If this assignment is already revoked.
        """
        if self.revoked_at is not None:
            raise ValidationError(f"RoleAssignment {self.id} is already revoked")
        self.revoked_at = datetime.now(UTC)

    @property
    def is_active(self) -> bool:
        """Return True if this assignment has not been revoked."""
        return self.revoked_at is None

    def __repr__(self) -> str:
        return f"<RoleAssignment user={self.user_id} role={self.role_id} active={self.is_active}>"


# ---------------------------------------------------------------------------
# ORM Model: TenantConfiguration (Enterprise Administration, spec §15)
# ---------------------------------------------------------------------------


class TenantConfiguration(Base):
    """
    A single tenant-level configuration key/value pair.

    Generic key/value shape (rather than one column per setting) so new
    configuration keys are additive rows, not schema changes — the same
    discipline already used for ``PolicyResult.triggered_rule_keys`` and
    other open-ended JSON columns in this codebase.
    """

    __tablename__ = "tenant_configurations"
    __table_args__ = {"schema": "identity"}

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    config_key: Mapped[str] = mapped_column(String(255), nullable=False)
    config_value: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    updated_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.users.id"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        config_key: str,
        config_value: dict[str, object],
        updated_by_user_id: UUID,
    ) -> TenantConfiguration:
        if not config_key or not config_key.strip():
            raise ValidationError("config_key must not be empty", field="config_key")
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            config_key=config_key.strip(),
            config_value=config_value,
            updated_by_user_id=updated_by_user_id,
            updated_at=datetime.now(UTC),
        )

    def update_value(
        self, config_value: dict[str, object], updated_by_user_id: UUID
    ) -> None:
        self.config_value = config_value
        self.updated_by_user_id = updated_by_user_id
        self.updated_at = datetime.now(UTC)

    def __repr__(self) -> str:
        return f"<TenantConfiguration key={self.config_key!r} tenant={self.tenant_id}>"


# ---------------------------------------------------------------------------
# ORM Model: ApiKey (Enterprise Administration, spec §15)
# ---------------------------------------------------------------------------


class ApiKey(Base):
    """
    A scoped, expiring, revocable API key for service-to-service integration
    (distinct from the ``SERVICE_ACCOUNT`` role — that governs a real
    authenticated principal; this governs a bearer credential a script or
    external system presents).

    The raw key is never stored — only ``hashed_key`` (same discipline as a
    password hash). The raw value is returned to the caller exactly once, at
    creation time, by ``IdentityService.create_api_key``.

    ``expires_at`` is NOT NULL by design (Constitution Principle V,
    least-privilege) — there is no "permanent, unexpiring key" creation path.
    """

    __tablename__ = "api_keys"
    __table_args__ = {"schema": "identity"}

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_key: Mapped[str] = mapped_column(String(128), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        name: str,
        hashed_key: str,
        scopes: list[str],
        expires_at: datetime,
        created_by_user_id: UUID,
    ) -> ApiKey:
        if not name or not name.strip():
            raise ValidationError("name must not be empty", field="name")
        if expires_at <= datetime.now(UTC):
            raise ValidationError("expires_at must be in the future", field="expires_at")
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            name=name.strip(),
            hashed_key=hashed_key,
            scopes=scopes,
            expires_at=expires_at,
            revoked_at=None,
            created_by_user_id=created_by_user_id,
            created_at=datetime.now(UTC),
        )

    def revoke(self) -> None:
        """Revoke this key. Idempotent — revoking twice is a no-op."""
        if self.revoked_at is None:
            self.revoked_at = datetime.now(UTC)

    @property
    def is_valid(self) -> bool:
        """Return ``True`` if the key is neither revoked nor expired."""
        return self.revoked_at is None and self.expires_at > datetime.now(UTC)

    def __repr__(self) -> str:
        return f"<ApiKey id={self.id} name={self.name!r} tenant={self.tenant_id}>"
