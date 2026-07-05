"""Unit tests for mil.kernel.providers.registry — ProviderRegistry (Sprint 8 hardening)."""

from __future__ import annotations

import pytest

from mil.kernel.providers.registry import ProviderRegistry, ProviderRegistryError


class _FakeOCRProvider:
    def version(self) -> str:
        return "fake-ocr-1.0.0"


class TestDuplicateRegistrationRejected:
    def test_registering_ocr_twice_raises(self) -> None:
        registry = ProviderRegistry()
        registry.register_ocr(_FakeOCRProvider())  # type: ignore[arg-type]
        with pytest.raises(ProviderRegistryError):
            registry.register_ocr(_FakeOCRProvider())  # type: ignore[arg-type]

    def test_first_registration_is_preserved_after_rejected_duplicate(self) -> None:
        registry = ProviderRegistry()
        first = _FakeOCRProvider()
        registry.register_ocr(first)  # type: ignore[arg-type]
        with pytest.raises(ProviderRegistryError):
            registry.register_ocr(_FakeOCRProvider())  # type: ignore[arg-type]
        assert registry.registered_providers()["ocr"] == type(first).__name__

    def test_different_provider_keys_do_not_collide(self) -> None:
        registry = ProviderRegistry()
        registry.register_ocr(_FakeOCRProvider())  # type: ignore[arg-type]
        # A different provider key must still register cleanly.
        registry.register_los_adapter(object())  # type: ignore[arg-type]
        assert registry.is_registered("ocr")
        assert registry.is_registered("los_adapter")


class TestValidate:
    def test_validate_raises_when_required_provider_missing(self) -> None:
        registry = ProviderRegistry()
        with pytest.raises(ProviderRegistryError):
            registry.validate()

    def test_validate_passes_when_all_required_providers_registered(self) -> None:
        registry = ProviderRegistry()
        registry.register_ocr(_FakeOCRProvider())  # type: ignore[arg-type]
        registry.register_extraction(object())  # type: ignore[arg-type]
        registry.register_inference(object())  # type: ignore[arg-type]
        registry.register_policy(object())  # type: ignore[arg-type]
        registry.register_storage(object())  # type: ignore[arg-type]
        registry.validate()  # should not raise
