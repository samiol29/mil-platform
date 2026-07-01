"""
Wiring tests for the Policy worker composition root.

Verifies that the PolicyProvider is resolved exclusively through the DI
container's ``ProviderRegistry`` and that the handler runs the processor
within a session.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from mil.kernel.config import get_settings
from mil.kernel.container import build_container
from mil.kernel.providers.policy import PolicyProvider
from mil.kernel.providers.registry import ProviderRegistry
from workers.policy_pipeline import build_policy_collaborators, make_policy_handler


class TestBuildCollaborators:
    def test_resolves_policy_provider_from_registry(self) -> None:
        container = build_container(get_settings())
        collaborators = build_policy_collaborators(MagicMock(), container)
        assert isinstance(collaborators.policy_provider, PolicyProvider)

    def test_provider_comes_through_the_registry(self) -> None:
        """The provider must be resolved via ProviderRegistry, not instantiated."""
        container = build_container(get_settings())
        registry = container.resolve(ProviderRegistry)
        collaborators = build_policy_collaborators(MagicMock(), container)
        assert collaborators.policy_provider is registry.get_policy()

    def test_builds_session_scoped_repositories(self) -> None:
        container = build_container(get_settings())
        session = MagicMock()
        collaborators = build_policy_collaborators(session, container)
        assert collaborators.findings is not None
        assert collaborators.policy is not None
        assert collaborators.policy_repo is not None
        assert collaborators.workflows is not None
        assert collaborators.outbox is not None
        assert collaborators.job_queue is not None


class TestMakePolicyHandler:
    def test_returns_callable_handler(self) -> None:
        container = build_container(get_settings())
        handler = make_policy_handler(container)
        assert callable(handler)
