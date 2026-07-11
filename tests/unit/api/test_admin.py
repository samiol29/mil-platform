"""Unit tests for Enterprise Administration API endpoints (spec 005 §15)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock  # noqa: TC003
from uuid import uuid4

from fastapi.testclient import TestClient  # noqa: TC002

from mil.identity.models import ApiKey, RoleAssignment, TenantConfiguration, User
from mil.kernel.errors import AuthorizationError, NotFoundError

TEST_TENANT_ID = uuid4()


def _make_user(**overrides: object) -> User:
    kwargs: dict[str, object] = {
        "tenant_id": TEST_TENANT_ID,
        "external_identity_id": "idp-001",
        "email_hash": "hash",
        "display_name": "Jane Reviewer",
    }
    kwargs.update(overrides)
    return User.create(**kwargs)  # type: ignore[arg-type]


class TestCreateUser:
    def test_returns_201(self, client: TestClient, mock_identity_service: MagicMock) -> None:
        mock_identity_service.create_user.return_value = _make_user()
        mock_identity_service.get_active_role_names.return_value = []
        response = client.post(
            "/v1/admin/users",
            json={
                "external_identity_id": "idp-001",
                "email": "reviewer@example.com",
                "display_name": "Jane Reviewer",
            },
        )
        assert response.status_code == 201
        assert response.json()["display_name"] == "Jane Reviewer"

    def test_authorization_error_returns_403(
        self, client: TestClient, mock_identity_service: MagicMock
    ) -> None:
        mock_identity_service.create_user.side_effect = AuthorizationError(
            "Permission denied: 'manage:users' is required"
        )
        response = client.post(
            "/v1/admin/users",
            json={
                "external_identity_id": "idp-001",
                "email": "reviewer@example.com",
                "display_name": "Jane Reviewer",
            },
        )
        assert response.status_code == 403


class TestListUsers:
    def test_returns_200(self, client: TestClient, mock_identity_service: MagicMock) -> None:
        mock_identity_service.list_users.return_value = [_make_user()]
        mock_identity_service.get_active_role_names.return_value = ["UNDERWRITER"]
        response = client.get("/v1/admin/users")
        assert response.status_code == 200
        assert response.json()["items"][0]["roles"] == ["UNDERWRITER"]


class TestDeactivateUser:
    def test_returns_200(self, client: TestClient, mock_identity_service: MagicMock) -> None:
        user = _make_user()
        mock_identity_service.get_user.return_value = user
        mock_identity_service.get_active_role_names.return_value = []
        response = client.patch(f"/v1/admin/users/{user.id}/deactivate")
        assert response.status_code == 200
        mock_identity_service.deactivate_user.assert_called_once()

    def test_not_found_returns_404(
        self, client: TestClient, mock_identity_service: MagicMock
    ) -> None:
        mock_identity_service.get_user.side_effect = NotFoundError("User", uuid4())
        response = client.patch(f"/v1/admin/users/{uuid4()}/deactivate")
        assert response.status_code == 404


class TestAssignRole:
    def test_self_escalation_returns_403(
        self, client: TestClient, mock_identity_service: MagicMock
    ) -> None:
        user = _make_user()
        mock_identity_service.get_user.return_value = user
        mock_identity_service.assign_role.side_effect = AuthorizationError(
            "A user may not assign a role to themselves (self-escalation prevention)."
        )
        response = client.post(
            f"/v1/admin/users/{user.id}/roles", json={"role_name": "ADMIN"}
        )
        assert response.status_code == 403

    def test_returns_201_on_success(
        self, client: TestClient, mock_identity_service: MagicMock
    ) -> None:
        user = _make_user()
        mock_identity_service.get_user.return_value = user
        mock_identity_service.assign_role.return_value = RoleAssignment.create(
            user_id=user.id, role_id=uuid4(), assigned_by=uuid4()
        )
        response = client.post(
            f"/v1/admin/users/{user.id}/roles", json={"role_name": "UNDERWRITER"}
        )
        assert response.status_code == 201
        assert response.json()["role_name"] == "UNDERWRITER"


class TestApiKeys:
    def test_create_returns_raw_key_once(
        self, client: TestClient, mock_identity_service: MagicMock
    ) -> None:
        api_key = ApiKey.create(
            tenant_id=TEST_TENANT_ID,
            name="los-sync",
            hashed_key="hashed",
            scopes=["manage:integration"],
            expires_at=datetime.now(UTC) + timedelta(days=30),
            created_by_user_id=uuid4(),
        )
        mock_identity_service.create_api_key.return_value = (api_key, "mil_raw_secret_value")
        response = client.post("/v1/admin/api-keys", json={"name": "los-sync", "ttl_days": 30})
        assert response.status_code == 201
        body = response.json()
        assert body["raw_key"] == "mil_raw_secret_value"

    def test_revoke_not_found_returns_404(
        self, client: TestClient, mock_identity_service: MagicMock
    ) -> None:
        mock_identity_service.get_api_key.side_effect = NotFoundError("ApiKey", uuid4())
        response = client.delete(f"/v1/admin/api-keys/{uuid4()}")
        assert response.status_code == 404


class TestTenantConfig:
    def test_set_returns_200(self, client: TestClient, mock_identity_service: MagicMock) -> None:
        config = TenantConfiguration.create(
            tenant_id=TEST_TENANT_ID,
            config_key="los.default",
            config_value={"vendor": "encompass"},
            updated_by_user_id=uuid4(),
        )
        mock_identity_service.set_tenant_configuration.return_value = config
        response = client.put(
            "/v1/admin/tenant-config/los.default",
            json={"config_value": {"vendor": "encompass"}},
        )
        assert response.status_code == 200
        assert response.json()["config_value"] == {"vendor": "encompass"}
