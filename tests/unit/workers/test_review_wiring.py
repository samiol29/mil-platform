"""
Wiring tests for the Review worker composition root.

Unlike the OCR, Extraction, Finding, and Policy workers, Review has no
provider to resolve from ``ProviderRegistry`` — these tests verify the
collaborators build correctly and the handler is callable.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from mil.kernel.config import get_settings
from mil.kernel.container import build_container
from mil.review.repository import ReviewRepository
from mil.review.service import ReviewService
from workers.review_pipeline import build_review_collaborators, make_review_handler


class TestBuildCollaborators:
    def test_builds_review_service(self) -> None:
        container = build_container(get_settings())
        collaborators = build_review_collaborators(MagicMock(), container)
        assert isinstance(collaborators.review, ReviewService)

    def test_builds_session_scoped_repositories(self) -> None:
        container = build_container(get_settings())
        session = MagicMock()
        collaborators = build_review_collaborators(session, container)
        assert isinstance(collaborators.reviews, ReviewRepository)
        assert collaborators.workflows is not None
        assert collaborators.outbox is not None


class TestMakeReviewHandler:
    def test_returns_callable_handler(self) -> None:
        container = build_container(get_settings())
        handler = make_review_handler(container)
        assert callable(handler)
