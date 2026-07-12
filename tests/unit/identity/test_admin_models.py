"""Unit tests for mil.identity.models — Enterprise Administration additions (spec 005 §15)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from mil.identity.models import ApiKey, RoleAssignment, TenantConfiguration, User
from mil.kernel.errors import ValidationError


def _make_user(**overrides: object) -> User:
    kwargs: dict[str, object] = {
        "tenant_id": uuid4(),
        "external_identity_id": "idp-sub-001",
        "email_hash": "deadbeef",
        "display_name": "Jane Reviewer",
    }
    kwargs.update(overrides)
    return User.create(**kwargs)  # type: ignore[arg-type]


class TestUser:
    def test_create_trims_and_defaults_active(self) -> None:
        user = _make_user(display_name="  Jane Reviewer  ")
        assert user.display_name == "Jane Reviewer"
        assert user.is_active is True

    def test_create_rejects_empty_display_name(self) -> None:
        with pytest.raises(ValidationError):
            _make_user(display_name="   ")

    def test_create_rejects_empty_external_identity_id(self) -> None:
        with pytest.raises(ValidationError):
            _make_user(external_identity_id="")

    def test_deactivate_is_idempotent(self) -> None:
        user = _make_user()
        user.deactivate()
        assert user.is_active is False
        user.deactivate()
        assert user.is_active is False


class TestRoleAssignment:
    def test_create_is_active(self) -> None:
        assignment = RoleAssignment.create(user_id=uuid4(), role_id=uuid4(), assigned_by=uuid4())
        assert assignment.is_active is True
        assert assignment.revoked_at is None

    def test_revoke_sets_revoked_at(self) -> None:
        assignment = RoleAssignment.create(user_id=uuid4(), role_id=uuid4(), assigned_by=uuid4())
        assignment.revoke()
        assert assignment.is_active is False

    def test_revoke_twice_raises(self) -> None:
        assignment = RoleAssignment.create(user_id=uuid4(), role_id=uuid4(), assigned_by=uuid4())
        assignment.revoke()
        with pytest.raises(ValidationError):
            assignment.revoke()


class TestTenantConfiguration:
    def test_create_and_update(self) -> None:
        config = TenantConfiguration.create(
            tenant_id=uuid4(),
            config_key="los.default_connection",
            config_value={"vendor": "encompass"},
            updated_by_user_id=uuid4(),
        )
        assert config.config_value == {"vendor": "encompass"}
        new_updater = uuid4()
        config.update_value({"vendor": "netoxygen"}, new_updater)
        assert config.config_value == {"vendor": "netoxygen"}
        assert config.updated_by_user_id == new_updater

    def test_create_rejects_empty_key(self) -> None:
        with pytest.raises(ValidationError):
            TenantConfiguration.create(
                tenant_id=uuid4(),
                config_key="  ",
                config_value={},
                updated_by_user_id=uuid4(),
            )


class TestApiKey:
    def test_create_requires_future_expiry(self) -> None:
        with pytest.raises(ValidationError):
            ApiKey.create(
                tenant_id=uuid4(),
                name="integration-test-key",
                hashed_key="abc123",
                scopes=["read:application"],
                expires_at=datetime.now(UTC) - timedelta(days=1),
                created_by_user_id=uuid4(),
            )

    def test_is_valid_true_when_unrevoked_and_unexpired(self) -> None:
        key = ApiKey.create(
            tenant_id=uuid4(),
            name="integration-test-key",
            hashed_key="abc123",
            scopes=[],
            expires_at=datetime.now(UTC) + timedelta(days=30),
            created_by_user_id=uuid4(),
        )
        assert key.is_valid is True

    def test_is_valid_false_after_revoke(self) -> None:
        key = ApiKey.create(
            tenant_id=uuid4(),
            name="integration-test-key",
            hashed_key="abc123",
            scopes=[],
            expires_at=datetime.now(UTC) + timedelta(days=30),
            created_by_user_id=uuid4(),
        )
        key.revoke()
        assert key.is_valid is False
        # idempotent
        key.revoke()
        assert key.is_valid is False
