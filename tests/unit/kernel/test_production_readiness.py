"""
Backend Freeze Patch v1.0 — startup safety guards.

Verifies that a development process assembles normally while a
non-development process refuses to start with development-only wiring:
mock/local providers (fix 2), the in-process message queue/bus (fix 3), or
no signature-verifying IdentityProvider (fix 1).
"""

from __future__ import annotations

import pytest

from main import _register_identity_provider
from mil.identity.provider import DevBearerIdentityProvider, IdentityProvider
from mil.kernel.config import Settings
from mil.kernel.container import (
    Container,
    ProductionReadinessError,
    _reject_development_providers,
    _reject_in_process_messaging,
    build_container,
)
from mil.kernel.event_bus import EventBus, InProcessEventBus
from mil.kernel.job_queue import InProcessJobQueue, JobQueue
from mil.kernel.providers.registry import ProviderRegistry, ProviderRegistryError


def _production_settings() -> Settings:
    """Return a production Settings with non-placeholder secrets."""
    return Settings(
        mil_env="production",
        mil_secret_key="prod-secret-key-not-a-placeholder",  # type: ignore[arg-type]
        postgres_password="prod-db-password",  # type: ignore[arg-type]
        mil_portal_secret_key="prod-portal-secret-key-not-a-placeholder",  # type: ignore[arg-type]
    )


class TestDevelopmentBuild:
    def test_development_build_succeeds(self) -> None:
        container = build_container(Settings())
        assert container.is_registered(ProviderRegistry)
        assert container.is_registered(JobQueue)


class TestProductionBuildFailsFast:
    def test_production_build_raises(self) -> None:
        # No production providers ship in this freeze, so a production build
        # must fail fast rather than start with development wiring.
        with pytest.raises((ProviderRegistryError, ProductionReadinessError)):
            build_container(_production_settings())


class TestRejectDevelopmentProviders:
    def test_mock_provider_is_rejected(self) -> None:
        from providers.ocr.mock_ocr import MockOCRProvider

        registry = ProviderRegistry()
        registry.register_ocr(MockOCRProvider())

        with pytest.raises(ProductionReadinessError):
            _reject_development_providers(registry)

    def test_empty_registry_is_accepted(self) -> None:
        # No development-only provider present — the guard passes (validation of
        # required providers is a separate step).
        _reject_development_providers(ProviderRegistry())


class TestRejectInProcessMessaging:
    def test_in_process_queue_is_rejected(self) -> None:
        container = Container()
        container.register_singleton(JobQueue, InProcessJobQueue)
        container.register_singleton(EventBus, InProcessEventBus)  # type: ignore[type-abstract]

        with pytest.raises(ProductionReadinessError):
            _reject_in_process_messaging(container)


class TestIdentityProviderRegistration:
    def test_development_registers_dev_provider(self) -> None:
        container = Container()
        _register_identity_provider(container, Settings())
        assert container.is_registered(IdentityProvider)
        assert isinstance(container.resolve(IdentityProvider), DevBearerIdentityProvider)  # type: ignore[type-abstract]

    def test_production_without_provider_raises(self) -> None:
        container = Container()
        with pytest.raises(ProductionReadinessError):
            _register_identity_provider(container, _production_settings())
