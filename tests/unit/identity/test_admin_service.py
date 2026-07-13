"""Unit tests for mil.identity.service — IdentityService (spec 005 §15)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from mil.identity.models import ApiKey, Role, RoleAssignment, TenantConfiguration, User
from mil.identity.service import IdentityService
from mil.kernel.errors import AuthorizationError, NotFoundError
from mil.kernel.security import AuthenticatedUser
from mil.kernel.security import Role as KernelRole


class FakeIdentityRepository:
    def __init__(self) -> None:
        self.users: dict[object, User] = {}
        self.roles: dict[object, Role] = {}
        self.roles_by_name: dict[tuple[object, str], Role] = {}
        self.assignments: list[RoleAssignment] = []
        self.tenant_configs: dict[tuple[object, str], TenantConfiguration] = {}
        self.api_keys: dict[object, ApiKey] = {}

    def save_user(self, user: User) -> None:
        self.users[user.id] = user

    def get_user_by_id(self, user_id: object) -> User | None:
        return self.users.get(user_id)

    def list_users_for_tenant(self, tenant_id: object) -> list[User]:
        return [u for u in self.users.values() if u.tenant_id == tenant_id]

    def save_role(self, role: Role) -> None:
        self.roles[role.id] = role
        self.roles_by_name[(role.tenant_id, role.name)] = role

    def get_role_by_id(self, role_id: object) -> Role | None:
        return self.roles.get(role_id)

    def get_role_by_name(self, tenant_id: object, name: str) -> Role | None:
        return self.roles_by_name.get((tenant_id, name))

    def save_role_assignment(self, assignment: RoleAssignment) -> None:
        self.assignments.append(assignment)

    def get_active_assignments_for_user(self, user_id: object) -> list[RoleAssignment]:
        return [a for a in self.assignments if a.user_id == user_id and a.is_active]

    def get_active_assignment(self, user_id: object, role_id: object) -> RoleAssignment | None:
        for a in self.assignments:
            if a.user_id == user_id and a.role_id == role_id and a.is_active:
                return a
        return None

    def save_tenant_configuration(self, config: TenantConfiguration) -> None:
        self.tenant_configs[(config.tenant_id, config.config_key)] = config

    def get_tenant_configuration(
        self, tenant_id: object, config_key: str
    ) -> TenantConfiguration | None:
        return self.tenant_configs.get((tenant_id, config_key))

    def list_tenant_configuration(self, tenant_id: object) -> list[TenantConfiguration]:
        return [c for (t, _), c in self.tenant_configs.items() if t == tenant_id]

    def save_api_key(self, api_key: ApiKey) -> None:
        self.api_keys[api_key.id] = api_key

    def get_api_key_by_id(self, api_key_id: object) -> ApiKey | None:
        return self.api_keys.get(api_key_id)

    def list_api_keys_for_tenant(self, tenant_id: object) -> list[ApiKey]:
        return [k for k in self.api_keys.values() if k.tenant_id == tenant_id]


class FakeAuditWriter:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record(self, **kwargs: object) -> object:
        self.records.append(kwargs)
        return object()


def _make_service() -> tuple[IdentityService, FakeIdentityRepository, FakeAuditWriter]:
    repo = FakeIdentityRepository()
    audit = FakeAuditWriter()
    return IdentityService(repo, audit), repo, audit  # type: ignore[arg-type]


def _admin_caller(tenant_id: object) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(), tenant_id=tenant_id, roles=frozenset({KernelRole.ADMIN})
    )


def _readonly_caller(tenant_id: object) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(), tenant_id=tenant_id, roles=frozenset({KernelRole.AUDIT_TEAM})
    )


class TestCreateUser:
    def test_admin_can_create_user(self) -> None:
        service, repo, audit = _make_service()
        tenant_id = uuid4()
        caller = _admin_caller(tenant_id)
        user = service.create_user(
            caller,
            external_identity_id="idp-001",
            email="reviewer@example.com",
            display_name="Jane Reviewer",
        )
        assert user.tenant_id == tenant_id
        assert repo.users[user.id] is user
        assert audit.records[-1]["event_type"] == "USER_CREATED"
        assert audit.records[-1]["actor_id"] == caller.user_id

    def test_non_admin_forbidden(self) -> None:
        service, _, _ = _make_service()
        caller = _readonly_caller(uuid4())
        with pytest.raises(AuthorizationError):
            service.create_user(
                caller,
                external_identity_id="idp-001",
                email="reviewer@example.com",
                display_name="Jane Reviewer",
            )


class TestAssignRole:
    def test_assign_role_records_audit_event(self) -> None:
        service, repo, audit = _make_service()
        tenant_id = uuid4()
        caller = _admin_caller(tenant_id)
        target = User.create(
            tenant_id=tenant_id,
            external_identity_id="idp-002",
            email_hash="x",
            display_name="Underwriter One",
        )
        repo.save_user(target)

        assignment = service.assign_role(caller, user=target, role_name="UNDERWRITER")

        assert assignment.user_id == target.id
        assert assignment.is_active is True
        assert audit.records[-1]["event_type"] == "ROLE_ASSIGNED"
        assert service.get_active_role_names(caller, target) == ["UNDERWRITER"]

    def test_self_escalation_is_rejected(self) -> None:
        service, repo, _ = _make_service()
        tenant_id = uuid4()
        caller = _admin_caller(tenant_id)
        # The caller attempts to assign a role to themselves.
        self_user = User.create(
            tenant_id=tenant_id,
            external_identity_id="idp-caller",
            email_hash="x",
            display_name="Admin Self",
        )
        object.__setattr__(self_user, "id", caller.user_id)
        repo.save_user(self_user)

        with pytest.raises(AuthorizationError):
            service.assign_role(caller, user=self_user, role_name="ADMIN")

    def test_assigning_same_role_twice_is_idempotent(self) -> None:
        service, repo, _audit = _make_service()
        tenant_id = uuid4()
        caller = _admin_caller(tenant_id)
        target = User.create(
            tenant_id=tenant_id,
            external_identity_id="idp-003",
            email_hash="x",
            display_name="Underwriter Two",
        )
        repo.save_user(target)

        first = service.assign_role(caller, user=target, role_name="UNDERWRITER")
        second = service.assign_role(caller, user=target, role_name="UNDERWRITER")

        assert first.id == second.id
        assert len(repo.assignments) == 1


class TestRevokeRole:
    def test_revoke_active_assignment(self) -> None:
        service, repo, audit = _make_service()
        tenant_id = uuid4()
        caller = _admin_caller(tenant_id)
        target = User.create(
            tenant_id=tenant_id,
            external_identity_id="idp-004",
            email_hash="x",
            display_name="Underwriter Three",
        )
        repo.save_user(target)
        assignment = service.assign_role(caller, user=target, role_name="UNDERWRITER")

        revoked = service.revoke_role(caller, user=target, role_id=assignment.role_id)

        assert revoked.is_active is False
        assert service.get_active_role_names(caller, target) == []
        assert audit.records[-1]["event_type"] == "ROLE_REVOKED"

    def test_revoke_nonexistent_assignment_raises_not_found(self) -> None:
        service, repo, _ = _make_service()
        tenant_id = uuid4()
        caller = _admin_caller(tenant_id)
        target = User.create(
            tenant_id=tenant_id,
            external_identity_id="idp-005",
            email_hash="x",
            display_name="Underwriter Four",
        )
        repo.save_user(target)

        with pytest.raises(NotFoundError):
            service.revoke_role(caller, user=target, role_id=uuid4())


class TestTenantConfiguration:
    def test_set_creates_then_updates(self) -> None:
        service, _repo, audit = _make_service()
        tenant_id = uuid4()
        caller = _admin_caller(tenant_id)

        created = service.set_tenant_configuration(
            caller, config_key="los.default", config_value={"vendor": "encompass"}
        )
        assert audit.records[-1]["event_type"] == "TENANT_CONFIG_CREATED"

        updated = service.set_tenant_configuration(
            caller, config_key="los.default", config_value={"vendor": "netoxygen"}
        )
        assert updated.id == created.id
        assert updated.config_value == {"vendor": "netoxygen"}
        assert audit.records[-1]["event_type"] == "TENANT_CONFIG_UPDATED"


class TestApiKeys:
    def test_create_returns_raw_key_once(self) -> None:
        service, _repo, audit = _make_service()
        tenant_id = uuid4()
        caller = _admin_caller(tenant_id)

        api_key, raw_key = service.create_api_key(
            caller, name="los-sync-key", scopes=["manage:integration"], ttl_days=30
        )

        assert raw_key.startswith("mil_")
        assert api_key.hashed_key != raw_key
        assert audit.records[-1]["event_type"] == "API_KEY_CREATED"

    def test_revoke_marks_invalid(self) -> None:
        service, _repo, audit = _make_service()
        tenant_id = uuid4()
        caller = _admin_caller(tenant_id)
        api_key, _ = service.create_api_key(caller, name="k", scopes=[], ttl_days=1)

        revoked = service.revoke_api_key(caller, api_key)

        assert revoked.is_valid is False
        assert audit.records[-1]["event_type"] == "API_KEY_REVOKED"
