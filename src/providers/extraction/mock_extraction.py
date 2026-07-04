"""
MockExtractionProvider — deterministic extraction provider, no longer wired by default.

``build_container`` no longer registers this provider in any environment —
``GeminiExtractionProvider`` (structured LLM extraction over real OCR text) is
the real extraction provider everywhere, including local development (see
``mil.kernel.container._build_extraction_provider``). Retained only as a
network-free test fixture and for defence-in-depth coverage of
``_reject_development_providers``, mirroring ``mock_ocr.py``.

MUST NOT be registered in staging or production containers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mil.kernel.providers.extraction import (
    EvidenceAttributes,
    ExtractionProvider,
    FieldLocation,
    make_evidence_attributes,
)

if TYPE_CHECKING:
    from mil.kernel.providers.ocr import OCRResult

_VERSION = "mock-extraction-1.0.0"

_EXTRACTION_METHOD = "mock-keyword-matcher"


class MockExtractionProvider(ExtractionProvider):
    """
    Deterministic extraction provider for development and testing.

    Parses the OCR result for a small set of well-known field patterns
    (``"Gross Monthly Income:"``, ``"Net Monthly Income:"``,
    ``"Employer:"``).  For each matched pattern, returns an
    ``EvidenceAttributes`` object with all seven provenance attributes
    populated.

    If no patterns are found in the OCR text (e.g. for blank or binary
    content), falls back to a single hard-coded placeholder evidence item
    so conformance tests always receive at least one result.

    Provenance attributes returned:
        1. source_document_ref  — echoed from ``ocr_result.document_ref``
        2. page_number          — page where the field was found
        3. field_location       — approximate bounding box (mocked values)
        4. extraction_confidence — fixed at 0.85
        5. extraction_method    — ``"mock-keyword-matcher"``
        6. extracted_at         — current UTC time at call
        7. extraction_version   — ``"mock-extraction-1.0.0"``
    """

    # Simple keyword → (field_name, field_location_name) mapping
    _PATTERNS: list[tuple[str, str]] = [
        ("Gross Monthly Income:", "gross_monthly_income"),
        ("Net Monthly Income:", "net_monthly_income"),
        ("Employer:", "employer_name"),
        ("Employee:", "employee_name"),
        ("Year-to-Date Gross:", "ytd_gross_income"),
    ]

    def extract_evidence(
        self,
        ocr_result: OCRResult,
        document_id: str,
    ) -> list[EvidenceAttributes]:
        extracted: list[EvidenceAttributes] = []

        for page in ocr_result.pages:
            for keyword, field_name in self._PATTERNS:
                if keyword not in page.text:
                    continue

                line = self._find_line(page.text, keyword)
                field_value = line.replace(keyword, "").strip()

                location = FieldLocation(
                    page_number=page.page_number,
                    field_name=field_name,
                    bounding_box=(0.1, 0.1 + len(extracted) * 0.08, 0.8, 0.06),
                )

                attrs = make_evidence_attributes(
                    field_name=field_name,
                    field_value=field_value,
                    document_id=document_id,
                    source_document_ref=ocr_result.document_ref,
                    page_number=page.page_number,
                    field_location=location,
                    extraction_confidence=0.85,
                    extraction_method=_EXTRACTION_METHOD,
                    extraction_version=_VERSION,
                )
                extracted.append(attrs)

        if not extracted:
            # Fallback: always return at least one evidence item for testing.
            extracted.append(
                make_evidence_attributes(
                    field_name="mock_placeholder",
                    field_value="no-pattern-matched",
                    document_id=document_id,
                    source_document_ref=ocr_result.document_ref,
                    page_number=1,
                    field_location=None,
                    extraction_confidence=0.0,
                    extraction_method=_EXTRACTION_METHOD,
                    extraction_version=_VERSION,
                )
            )

        return extracted

    def version(self) -> str:
        return _VERSION

    @staticmethod
    def _find_line(text: str, keyword: str) -> str:
        for line in text.splitlines():
            if keyword in line:
                return line
        return keyword
