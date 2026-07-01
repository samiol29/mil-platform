"""
Provider conformance test configuration.

Fixtures that supply concrete provider implementations for conformance tests.
All tests under ``tests/providers/`` are automatically marked ``providers``
by the ``_providers_marker`` auto-use fixture.

To add a new provider conformance test:
  1. Add a fixture below that instantiates the concrete provider.
  2. Create ``tests/providers/test_<provider>_conformance.py``.
  3. Use the fixture as a parameter in the test class or function.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from providers.extraction.mock_extraction import MockExtractionProvider
from providers.inference.mock_inference import MockInferenceProvider
from providers.los.mock_los import MockLOSAdapter
from providers.ocr.mock_ocr import MockOCRProvider
from providers.policy.mock_policy import MockPolicyProvider
from providers.storage.local_storage import LocalStorageProvider


@pytest.fixture(autouse=True)
def _providers_marker(request: pytest.FixtureRequest) -> None:
    """Auto-apply the 'providers' marker to all tests under tests/providers/."""
    request.node.add_marker(pytest.mark.providers)


# ---------------------------------------------------------------------------
# Provider fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ocr_provider() -> MockOCRProvider:
    """Concrete OCRProvider implementation under conformance test."""
    return MockOCRProvider()


@pytest.fixture
def extraction_provider() -> MockExtractionProvider:
    """Concrete ExtractionProvider implementation under conformance test."""
    return MockExtractionProvider()


@pytest.fixture
def inference_provider() -> MockInferenceProvider:
    """Concrete InferenceProvider implementation under conformance test."""
    return MockInferenceProvider()


@pytest.fixture
def policy_provider() -> MockPolicyProvider:
    """Concrete PolicyProvider implementation under conformance test."""
    return MockPolicyProvider()


@pytest.fixture
def storage_provider(tmp_path: Path) -> LocalStorageProvider:
    """Concrete StorageProvider using a per-test temporary directory."""
    return LocalStorageProvider(base_path=tmp_path / "mil-test-storage")


@pytest.fixture
def los_adapter() -> MockLOSAdapter:
    """Concrete LOSAdapter implementation under conformance test."""
    return MockLOSAdapter()


# ---------------------------------------------------------------------------
# Shared test data helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Minimal bytes payload used as a stand-in for a PDF document."""
    return b"%PDF-1.4 mock document content for conformance testing"


@pytest.fixture
def sample_content_hash(sample_pdf_bytes: bytes) -> str:
    """SHA-256 hex digest of ``sample_pdf_bytes``."""
    return hashlib.sha256(sample_pdf_bytes).hexdigest()
