"""Unit tests for auth and system endpoints."""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from main import create_app
from mil.api.deps import get_application_service, get_document_service
from mil.kernel.security import AuthenticatedUser  # noqa: TC001

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_token(
    user_id: object = None,
    tenant_id: object = None,
    roles: list[str] | None = None,
    email: str = "user@test.com",
    display_name: str = "Test User",
) -> str:
    uid = str(user_id or uuid4())
    tid = str(tenant_id or uuid4())
    payload = {
        "user_id": uid,
        "tenant_id": tid,
        "roles": roles or ["ADMIN"],
        "email": email,
        "display_name": display_name,
    }
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


def _make_client_with_no_auth_override() -> TestClient:
    """TestClient WITHOUT the current_user override — uses real auth dep."""
    app = create_app()
    app.dependency_overrides[get_application_service] = lambda: MagicMock()
    app.dependency_overrides[get_document_service] = lambda: MagicMock()
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_returns_200(self, client: TestClient) -> None:
        response = client.get("/v1/health")
        assert response.status_code == 200

    def test_returns_ok_status(self, client: TestClient) -> None:
        data = client.get("/v1/health").json()
        assert data["status"] == "ok"

    def test_no_auth_required(self) -> None:
        # Plain instantiation (no `with` block): entering TestClient as a
        # context manager runs the real ASGI lifespan (main.lifespan), which
        # opens a real database connection — unit tests must never depend on
        # live infrastructure. /v1/health takes no dependencies, so this
        # assertion needs nothing lifespan would provide anyway.
        app = create_app()
        c = TestClient(app, raise_server_exceptions=True)
        response = c.get("/v1/health")
        assert response.status_code == 200

    def test_returns_version(self, client: TestClient) -> None:
        data = client.get("/v1/health").json()
        assert "version" in data

    def test_returns_environment(self, client: TestClient) -> None:
        data = client.get("/v1/health").json()
        assert "environment" in data


# ---------------------------------------------------------------------------
# GET /v1/me
# ---------------------------------------------------------------------------


class TestGetMe:
    def test_returns_200_when_authenticated(self, client: TestClient) -> None:
        response = client.get("/v1/me")
        assert response.status_code == 200

    def test_returns_user_id(self, client: TestClient, current_user: AuthenticatedUser) -> None:
        data = client.get("/v1/me").json()
        assert data["user_id"] == str(current_user.user_id)

    def test_returns_tenant_id(self, client: TestClient, current_user: AuthenticatedUser) -> None:
        data = client.get("/v1/me").json()
        assert data["tenant_id"] == str(current_user.tenant_id)

    def test_returns_roles(self, client: TestClient, current_user: AuthenticatedUser) -> None:
        data = client.get("/v1/me").json()
        assert set(data["roles"]) == current_user.roles

    def test_returns_email(self, client: TestClient, current_user: AuthenticatedUser) -> None:
        data = client.get("/v1/me").json()
        assert data["email"] == current_user.email

    def test_returns_display_name(
        self, client: TestClient, current_user: AuthenticatedUser
    ) -> None:
        data = client.get("/v1/me").json()
        assert data["display_name"] == current_user.display_name

    def test_missing_auth_returns_401(self) -> None:
        tc = _make_client_with_no_auth_override()
        response = tc.get("/v1/me")
        assert response.status_code == 401

    def test_invalid_scheme_returns_401(self) -> None:
        tc = _make_client_with_no_auth_override()
        response = tc.get("/v1/me", headers={"Authorization": "Basic abc123"})
        assert response.status_code == 401

    def test_dev_token_resolves_in_dev_mode(self) -> None:
        tc = _make_client_with_no_auth_override()
        response = tc.get("/v1/me", headers={"Authorization": "Bearer dev"})
        # dev token accepted in development mode
        assert response.status_code == 200
        data = response.json()
        assert "ADMIN" in data["roles"]

    def test_valid_bearer_token_accepted(self) -> None:
        uid = uuid4()
        tid = uuid4()
        token = _make_token(user_id=uid, tenant_id=tid, roles=["RELATIONSHIP_MANAGER"])
        tc = _make_client_with_no_auth_override()
        response = tc.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == str(uid)
        assert data["tenant_id"] == str(tid)
        assert data["roles"] == ["RELATIONSHIP_MANAGER"]

    def test_malformed_token_returns_401(self) -> None:
        tc = _make_client_with_no_auth_override()
        response = tc.get("/v1/me", headers={"Authorization": "Bearer not-valid-base64!!!"})
        assert response.status_code == 401

    def test_token_missing_user_id_returns_401(self) -> None:
        payload = base64.urlsafe_b64encode(
            json.dumps({"tenant_id": str(uuid4()), "roles": ["ADMIN"]}).encode()
        ).decode()
        tc = _make_client_with_no_auth_override()
        response = tc.get("/v1/me", headers={"Authorization": f"Bearer {payload}"})
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# OpenAPI generation
# ---------------------------------------------------------------------------


class TestOpenAPI:
    def test_openapi_json_is_reachable(self, client: TestClient) -> None:
        response = client.get("/v1/openapi.json")
        assert response.status_code == 200

    def test_openapi_has_title(self, client: TestClient) -> None:
        data = client.get("/v1/openapi.json").json()
        assert "Mortgage Intelligence Layer" in data["info"]["title"]

    def test_openapi_has_health_endpoint(self, client: TestClient) -> None:
        data = client.get("/v1/openapi.json").json()
        assert "/v1/health" in data["paths"]

    def test_openapi_has_me_endpoint(self, client: TestClient) -> None:
        data = client.get("/v1/openapi.json").json()
        assert "/v1/me" in data["paths"]

    def test_openapi_has_applications_endpoints(self, client: TestClient) -> None:
        data = client.get("/v1/openapi.json").json()
        assert "/v1/applications" in data["paths"]

    def test_openapi_has_documents_endpoint(self, client: TestClient) -> None:
        data = client.get("/v1/openapi.json").json()
        paths = data["paths"]
        assert any("documents" in path for path in paths)

    def test_swagger_ui_is_reachable(self, client: TestClient) -> None:
        response = client.get("/v1/docs")
        assert response.status_code == 200
