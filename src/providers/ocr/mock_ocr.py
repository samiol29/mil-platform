"""
MockOCRProvider — deterministic OCR provider, no longer wired by default.

``build_container`` no longer registers this provider in any environment —
``GeminiOCRProvider`` (native multimodal document understanding) is the real
OCR provider everywhere, including local development (see
``mil.kernel.container._build_ocr_provider``). This class is retained only as:

  - a fixture for tests that want a deterministic, network-free OCR result
    without constructing a Gemini provider, and
  - the subject of ``tests/unit/kernel/test_production_readiness.py``'s
    defence-in-depth check that ``_reject_development_providers`` correctly
    classifies it as development-only if it were ever mistakenly registered.

MUST NOT be registered in staging or production containers.
"""

from __future__ import annotations

from datetime import UTC, datetime

from mil.kernel.providers.ocr import OCRProvider, OCRResult, PageLayout, PageText

_VERSION = "mock-ocr-1.0.0"

_MOCK_PAGE_1_TEXT = (
    "PAYSLIP\n"
    "Employee: John Applicant\n"
    "Period: January 2026\n"
    "Gross Monthly Income: 5000.00\n"
    "Net Monthly Income: 3800.00\n"
    "Employer: Acme Corporation\n"
)

_MOCK_PAGE_2_TEXT = (
    "PAYSLIP (continued)\n"
    "Year-to-Date Gross: 5000.00\n"
    "Tax Withheld: 1200.00\n"
    "National Insurance: 480.00\n"
)


class MockOCRProvider(OCRProvider):
    """
    Deterministic OCR provider for development and testing.

    Returns a fixed two-page ``OCRResult`` regardless of the document content.
    The ``provider_version`` is ``"mock-ocr-1.0.0"`` in all results.

    Conformance test usage::

        provider = MockOCRProvider()
        result = provider.process_document("doc-ref-001", b"any-bytes")
        assert result.provider_version == "mock-ocr-1.0.0"
        assert result.page_count == 2
    """

    def process_document(self, document_ref: str, content: bytes) -> OCRResult:
        layout_1 = PageLayout(page_number=1, width_points=595.0, height_points=842.0)
        layout_2 = PageLayout(page_number=2, width_points=595.0, height_points=842.0)

        page_1 = PageText(
            page_number=1,
            text=_MOCK_PAGE_1_TEXT,
            layout=layout_1,
            word_count=len(_MOCK_PAGE_1_TEXT.split()),
        )
        page_2 = PageText(
            page_number=2,
            text=_MOCK_PAGE_2_TEXT,
            layout=layout_2,
            word_count=len(_MOCK_PAGE_2_TEXT.split()),
        )

        return OCRResult(
            document_ref=document_ref,
            pages=(page_1, page_2),
            provider_version=_VERSION,
            processed_at=datetime.now(UTC),
        )

    def version(self) -> str:
        return _VERSION
