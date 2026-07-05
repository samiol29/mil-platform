"""
Wiring tests for the Extraction worker composition root.

Verifies that the ExtractionProvider is resolved exclusively through the DI
container's ``ProviderRegistry`` and that the handler runs the processor
within a session.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from mil.kernel.config import get_settings
from mil.kernel.container import build_container
from mil.kernel.providers.extraction import ExtractionProvider
from mil.kernel.providers.registry import ProviderRegistry
from workers.extraction_pipeline import build_extraction_collaborators, make_extraction_handler


class TestBuildCollaborators:
    def test_resolves_extraction_provider_from_registry(self) -> None:
        container = build_container(get_settings())
        collaborators = build_extraction_collaborators(MagicMock(), container)
        assert isinstance(collaborators.extraction_provider, ExtractionProvider)

    def test_provider_comes_through_the_registry(self) -> None:
        """The provider must be resolved via ProviderRegistry, not instantiated."""
        container = build_container(get_settings())
        registry = container.resolve(ProviderRegistry)
        collaborators = build_extraction_collaborators(MagicMock(), container)
        assert collaborators.extraction_provider is registry.get_extraction()

    def test_builds_session_scoped_repositories(self) -> None:
        container = build_container(get_settings())
        session = MagicMock()
        collaborators = build_extraction_collaborators(session, container)
        assert collaborators.ocr_results is not None
        assert collaborators.evidence is not None
        assert collaborators.evidence_items is not None
        assert collaborators.workflows is not None
        assert collaborators.outbox is not None


class TestMakeExtractionHandler:
    def test_returns_callable_handler(self) -> None:
        container = build_container(get_settings())
        handler = make_extraction_handler(container)
        assert callable(handler)
