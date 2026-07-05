"""Unit tests for mil.kernel.container — DI container and build_container factory."""

from __future__ import annotations

import pytest

from mil.kernel.config import Settings, get_settings
from mil.kernel.container import Container, build_container
from mil.kernel.errors import DependencyNotRegisteredError
from mil.kernel.metrics import InMemoryMetricEmitter
from mil.kernel.observability import MetricEmitter

# ---------------------------------------------------------------------------
# Container — registration and resolution
# ---------------------------------------------------------------------------


class TestContainerSingleton:
    def test_register_and_resolve_instance(self) -> None:
        container = Container()

        class MyService:
            pass

        instance = MyService()
        container.register_instance(MyService, instance)
        resolved = container.resolve(MyService)
        assert resolved is instance

    def test_register_singleton_factory_called_once(self) -> None:
        container = Container()
        call_count = 0

        class MyService:
            pass

        def factory() -> MyService:
            nonlocal call_count
            call_count += 1
            return MyService()

        container.register_singleton(MyService, factory)
        r1 = container.resolve(MyService)
        r2 = container.resolve(MyService)
        assert r1 is r2
        assert call_count == 1

    def test_register_instance_returns_same_object(self) -> None:
        container = Container()

        class Svc:
            pass

        svc = Svc()
        container.register_instance(Svc, svc)
        assert container.resolve(Svc) is svc
        assert container.resolve(Svc) is svc


class TestContainerTransient:
    def test_transient_factory_called_each_resolve(self) -> None:
        container = Container()
        call_count = 0

        class Svc:
            pass

        def factory() -> Svc:
            nonlocal call_count
            call_count += 1
            return Svc()

        container.register_transient(Svc, factory)
        r1 = container.resolve(Svc)
        r2 = container.resolve(Svc)
        assert r1 is not r2
        assert call_count == 2


class TestContainerResolutionErrors:
    def test_resolve_unregistered_raises_dependency_not_registered(self) -> None:
        container = Container()

        class Unknown:
            pass

        with pytest.raises(DependencyNotRegisteredError) as exc_info:
            container.resolve(Unknown)
        assert "Unknown" in exc_info.value.message

    def test_unregistered_error_is_mil_error(self) -> None:
        container = Container()

        class Svc:
            pass

        with pytest.raises(DependencyNotRegisteredError):
            container.resolve(Svc)


class TestContainerInspection:
    def test_is_registered_true(self) -> None:
        container = Container()

        class Svc:
            pass

        container.register_instance(Svc, Svc())
        assert container.is_registered(Svc) is True

    def test_is_registered_false(self) -> None:
        container = Container()

        class Svc:
            pass

        assert container.is_registered(Svc) is False

    def test_registered_interfaces_empty_initially(self) -> None:
        container = Container()
        assert container.registered_interfaces() == []

    def test_registered_interfaces_lists_all(self) -> None:
        container = Container()

        class A:
            pass

        class B:
            pass

        container.register_instance(A, A())
        container.register_instance(B, B())
        interfaces = container.registered_interfaces()
        assert A in interfaces
        assert B in interfaces
        assert len(interfaces) == 2

    def test_overwrite_binding(self) -> None:
        """Re-registering an interface replaces the previous binding."""
        container = Container()

        class Svc:
            value: str

        s1 = Svc()
        s1.value = "first"
        s2 = Svc()
        s2.value = "second"

        container.register_instance(Svc, s1)
        container.register_instance(Svc, s2)
        assert container.resolve(Svc).value == "second"


# ---------------------------------------------------------------------------
# build_container factory
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield  # type: ignore[misc]
    get_settings.cache_clear()


class TestBuildContainer:
    def test_build_container_returns_container(self) -> None:
        settings = Settings()
        container = build_container(settings)
        assert isinstance(container, Container)

    def test_settings_registered_as_singleton(self) -> None:
        settings = Settings()
        container = build_container(settings)
        assert container.is_registered(Settings)
        resolved = container.resolve(Settings)
        assert resolved is settings

    def test_metric_emitter_registered(self) -> None:
        settings = Settings()
        container = build_container(settings)
        assert container.is_registered(MetricEmitter)

    def test_default_metric_emitter_is_in_memory(self) -> None:
        settings = Settings()
        container = build_container(settings)
        emitter = container.resolve(MetricEmitter)
        assert isinstance(emitter, InMemoryMetricEmitter)

    def test_metric_emitter_is_singleton(self) -> None:
        settings = Settings()
        container = build_container(settings)
        e1 = container.resolve(MetricEmitter)
        e2 = container.resolve(MetricEmitter)
        assert e1 is e2

    def test_multiple_containers_are_independent(self) -> None:
        settings = Settings()
        c1 = build_container(settings)
        c2 = build_container(settings)

        class ExtraService:
            pass

        c1.register_instance(ExtraService, ExtraService())
        assert c1.is_registered(ExtraService) is True
        assert c2.is_registered(ExtraService) is False
