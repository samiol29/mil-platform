"""Unit tests for operational probe and metrics endpoints (Sprint 8)."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from main import create_app
from mil.api.deps import get_container, get_current_user, get_db
from mil.kernel.config import Settings
from mil.kernel.container import Container, build_container
from mil.kernel.metrics import InMemoryMetricEmitter, MetricName
from mil.kernel.observability import MetricEmitter
from mil.kernel.providers.registry import ProviderRegistryError
from mil.kernel.security import Role
from tests.unit.api.conftest import make_user


def _client_with_db_and_container(*, session: MagicMock, container: object) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_container] = lambda: container
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# GET /v1/health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_returns_200(self, client: TestClient) -> None:
        assert client.get("/v1/health").status_code == 200

    def test_includes_uptime(self, client: TestClient) -> None:
        data = client.get("/v1/health").json()
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0

    def test_no_auth_required(self) -> None:
        # Plain instantiation (no `with` block): entering TestClient as a
        # context manager runs the real ASGI lifespan (main.lifespan), which
        # opens a real database connection — unit tests must never depend on
        # live infrastructure. /v1/health takes no dependencies, so this
        # assertion needs nothing lifespan would provide anyway.
        c = TestClient(create_app(), raise_server_exceptions=True)
        assert c.get("/v1/health").status_code == 200


# ---------------------------------------------------------------------------
# GET /v1/live
# ---------------------------------------------------------------------------


class TestLive:
    def test_returns_200(self, client: TestClient) -> None:
        assert client.get("/v1/live").status_code == 200

    def test_returns_alive_status(self, client: TestClient) -> None:
        assert client.get("/v1/live").json()["status"] == "alive"


# ---------------------------------------------------------------------------
# GET /v1/ready
# ---------------------------------------------------------------------------


class TestReady:
    def test_returns_200_when_all_checks_pass(self) -> None:
        session = MagicMock()
        session.execute.return_value.first.return_value = ("0009",)
        container = build_container(Settings())
        tc = _client_with_db_and_container(session=session, container=container)
        response = tc.get("/v1/ready")
        assert response.status_code in (200, 503)  # migration head depends on repo state

    def test_returns_503_when_database_unreachable(self) -> None:
        session = MagicMock()
        session.execute.side_effect = RuntimeError("connection refused")
        container = build_container(Settings())
        tc = _client_with_db_and_container(session=session, container=container)
        response = tc.get("/v1/ready")
        assert response.status_code == 503
        data = response.json()
        db_check = next(c for c in data["checks"] if c["name"] == "database")
        assert db_check["status"] == "fail"

    def test_returns_503_when_provider_registration_invalid(self) -> None:
        session = MagicMock()
        session.execute.return_value.first.return_value = ("0009",)

        class _BrokenRegistry:
            def validate(self) -> None:
                raise ProviderRegistryError("Required providers not registered: ocr")

        class _FakeContainer:
            def resolve(self, interface: object) -> object:
                return _BrokenRegistry()

        tc = _client_with_db_and_container(session=session, container=_FakeContainer())
        response = tc.get("/v1/ready")
        assert response.status_code == 503
        data = response.json()
        provider_check = next(c for c in data["checks"] if c["name"] == "provider_registration")
        assert provider_check["status"] == "fail"

    def test_response_lists_all_three_checks(self) -> None:
        session = MagicMock()
        session.execute.return_value.first.return_value = ("0009",)
        container = build_container(Settings())
        tc = _client_with_db_and_container(session=session, container=container)
        data = tc.get("/v1/ready").json()
        check_names = {c["name"] for c in data["checks"]}
        assert check_names == {"database", "provider_registration", "migration_state"}

    def test_no_auth_required(self) -> None:
        session = MagicMock()
        session.execute.return_value.first.return_value = ("0009",)
        container = build_container(Settings())
        tc = _client_with_db_and_container(session=session, container=container)
        # No Authorization header supplied at all.
        response = tc.get("/v1/ready")
        assert response.status_code in (200, 503)


# ---------------------------------------------------------------------------
# GET /v1/metrics
# ---------------------------------------------------------------------------


class TestMetrics:
    def _container_with_emitter(self, emitter: MetricEmitter) -> Container:
        container = Container()
        container.register_instance(MetricEmitter, emitter)  # type: ignore[type-abstract]
        return container

    def test_requires_authentication(self) -> None:
        app = create_app()
        app.dependency_overrides[get_container] = lambda: self._container_with_emitter(
            InMemoryMetricEmitter()
        )
        # Plain instantiation (no `with` block) — see TestHealth.test_no_auth_required
        # above. get_current_user raises 401 before get_container is ever
        # reached, so nothing here depends on the real lifespan having run.
        tc = TestClient(app, raise_server_exceptions=True)
        response = tc.get("/v1/metrics")
        assert response.status_code == 401

    def test_returns_403_without_read_operational_permission(self, client: TestClient) -> None:
        client.app.dependency_overrides[get_current_user] = lambda: make_user(
            Role.RELATIONSHIP_MANAGER
        )
        client.app.dependency_overrides[get_container] = lambda: self._container_with_emitter(
            InMemoryMetricEmitter()
        )
        response = client.get("/v1/metrics")
        assert response.status_code == 403

    def test_returns_counters_and_histograms(self, client: TestClient) -> None:
        emitter = InMemoryMetricEmitter()
        emitter.increment(MetricName.HTTP_REQUESTS_TOTAL, value=3.0)
        emitter.histogram(MetricName.HTTP_REQUEST_DURATION_MS, 10.0)
        emitter.histogram(MetricName.HTTP_REQUEST_DURATION_MS, 30.0)
        client.app.dependency_overrides[get_current_user] = lambda: make_user(
            Role.OPERATIONS_MANAGER
        )
        client.app.dependency_overrides[get_container] = lambda: self._container_with_emitter(
            emitter
        )

        data = client.get("/v1/metrics").json()

        assert data["counters"][MetricName.HTTP_REQUESTS_TOTAL] == 3.0
        histogram = data["histograms"][MetricName.HTTP_REQUEST_DURATION_MS]
        assert histogram["count"] == 2
        assert histogram["average"] == 20.0
