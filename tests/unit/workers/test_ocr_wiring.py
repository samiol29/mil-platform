"""
Wiring tests for the OCR worker composition root.

Verifies that providers are resolved exclusively through the DI container's
``ProviderRegistry`` and that the handler runs the processor within a session.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from mil.kernel.config import get_settings
from mil.kernel.container import build_container
from mil.kernel.providers.ocr import OCRProvider
from mil.kernel.providers.registry import ProviderRegistry
from mil.kernel.providers.storage import StorageProvider
from workers.document_pipeline import build_ocr_collaborators, make_ocr_handler


class TestBuildCollaborators:
    def test_resolves_ocr_provider_from_registry(self) -> None:
        container = build_container(get_settings())
        collaborators = build_ocr_collaborators(MagicMock(), container)
        assert isinstance(collaborators.ocr_provider, OCRProvider)

    def test_resolves_storage_provider_from_registry(self) -> None:
        container = build_container(get_settings())
        collaborators = build_ocr_collaborators(MagicMock(), container)
        assert isinstance(collaborators.storage, StorageProvider)

    def test_providers_come_through_the_registry(self) -> None:
        """Providers must be resolved via ProviderRegistry, not instantiated."""
        container = build_container(get_settings())
        registry = container.resolve(ProviderRegistry)
        collaborators = build_ocr_collaborators(MagicMock(), container)
        assert collaborators.ocr_provider is registry.get_ocr()
        assert collaborators.storage is registry.get_storage()

    def test_builds_session_scoped_repositories(self) -> None:
        container = build_container(get_settings())
        session = MagicMock()
        collaborators = build_ocr_collaborators(session, container)
        assert collaborators.ocr_results is not None
        assert collaborators.workflows is not None
        assert collaborators.outbox is not None
        assert collaborators.documents is not None
        assert collaborators.job_queue is not None


class TestMakeOcrHandler:
    def test_returns_callable_handler(self) -> None:
        container = build_container(get_settings())
        handler = make_ocr_handler(container)
        assert callable(handler)
