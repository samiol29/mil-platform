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

import httpx
import pytest

if TYPE_CHECKING:
    from pathlib import Path

from providers.extraction.mock_extraction import MockExtractionProvider
from providers.inference.gemini_inference import GeminiInferenceProvider
from providers.los.mock_los import MockLOSAdapter
from providers.ocr.mock_ocr import MockOCRProvider
from providers.policy.mock_policy import MockPolicyProvider
from providers.storage.local_storage import LocalStorageProvider


def _gemini_ok_response(request: httpx.Request) -> httpx.Response:
    """
    A fixed, well-formed Gemini ``generateContent`` success body.

    The answer text echoes ``ev-001`` so citation extraction produces a
    non-empty result for the default conformance context (whose grounding
    includes ``ev-001``), while remaining a strict subset of the context refs.
    """
    return httpx.Response(
        200,
        json={
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Based on [ev-001], the income appears consistent."}],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                }
            ]
        },
    )


def build_gemini_provider_with_handler(
    handler: object, *, model: str = "gemini-2.5-flash", **kwargs: object
) -> GeminiInferenceProvider:
    """
    Construct a ``GeminiInferenceProvider`` whose HTTP client is backed by an
    ``httpx.MockTransport`` — no network, fully deterministic.

    ``sleep`` is stubbed to a no-op so retry tests do not actually wait.
    """
    client = httpx.Client(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]
    return GeminiInferenceProvider(
        api_key="test-api-key",
        model=model,
        client=client,
        sleep=lambda _seconds: None,
        **kwargs,  # type: ignore[arg-type]
    )


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
def inference_provider() -> GeminiInferenceProvider:
    """
    Concrete InferenceProvider under conformance test.

    ``GeminiInferenceProvider`` is exercised against a deterministic in-memory
    ``httpx.MockTransport`` so the conformance suite verifies the *provider
    abstraction* (contract, attribution, citation scoping) without a network or
    a real Gemini key.
    """
    return build_gemini_provider_with_handler(_gemini_ok_response)


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
