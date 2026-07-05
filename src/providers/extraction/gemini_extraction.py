"""
GeminiExtractionProvider — LLM-based structured mortgage evidence extraction.

Replaces ``MockExtractionProvider`` as the platform's real ``ExtractionProvider``.
Takes the raw per-page text an ``OCRProvider`` already produced (this provider
never re-reads the document's bytes or calls OCR again — one Gemini call per
pipeline stage, never two calls doing the same job) and asks Gemini to extract
every mortgage-relevant fact as a typed, schema-constrained JSON array. Each
fact becomes one ``EvidenceAttributes`` object with all seven Principle II
provenance attributes populated.

Evidence taxonomy (``_EvidenceType``): borrower, co-borrower, employer,
employment, income, loan amount, interest rate, purchase price, down payment,
assets, liabilities, property address, declarations, signatures, dates, and
document type — the canonical set of facts downstream modules (underwriting,
policy evaluation, findings, Copilot grounding) need without re-asking an LLM
to rediscover something already extracted once.

Architectural boundary: every Gemini-specific detail (endpoint, JSON schema,
prompt) lives only in this module. It satisfies the existing, unchanged
``ExtractionProvider`` interface (``mil.kernel.providers.extraction``) — the
Extraction stage worker, ``EvidenceService``, and everything downstream is
unaware Gemini exists.

Dependency rule: imports from ``httpx``, ``mil.kernel``, ``providers.gemini_client``,
and the Python standard library only.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from mil.kernel.errors import ProviderError
from mil.kernel.providers.extraction import (
    EvidenceAttributes,
    ExtractionProvider,
    FieldLocation,
    make_evidence_attributes,
)
from providers.gemini_client import GeminiHttpClient

if TYPE_CHECKING:
    from collections.abc import Callable

    import httpx

    from mil.kernel.providers.ocr import OCRResult

_PROVIDER_NAME: Final = "GeminiExtractionProvider"
_EXTRACTION_METHOD: Final = "gemini-document-understanding"

# The canonical mortgage evidence taxonomy. Kept as plain strings (not a
# domain enum) so this module has zero dependency on any bounded context —
# ``field_name`` on EvidenceAttributes is just a machine-readable identifier.
EVIDENCE_TYPES: Final[tuple[str, ...]] = (
    "BORROWER_NAME",
    "CO_BORROWER_NAME",
    "EMPLOYER_NAME",
    "EMPLOYMENT_STATUS",
    "MONTHLY_INCOME",
    "ANNUAL_INCOME",
    "LOAN_AMOUNT",
    "INTEREST_RATE",
    "PURCHASE_PRICE",
    "DOWN_PAYMENT",
    "ASSETS",
    "LIABILITIES",
    "PROPERTY_ADDRESS",
    "DOCUMENT_TYPE",
    "DECLARATION",
    "SIGNATURE_PRESENT",
    "DOCUMENT_DATE",
    "OTHER",
)

_SYSTEM_INSTRUCTION: Final = (
    "You are a precise mortgage-document fact extractor for a regulated "
    "lending platform. You are given the raw, page-numbered text of one "
    "source document. Extract every fact that matches one of the allowed "
    "evidence_type values. Do not invent facts that are not present in the "
    "text. Do not perform arithmetic or inference beyond what is written. "
    "For each fact, report the exact page number (as given in the input) it "
    "was found on, and a confidence in [0.0, 1.0] reflecting how literally "
    "the text supports the value (1.0 = verbatim figure/name; lower for "
    "paraphrased or partially legible text). If nothing in the document "
    "matches an evidence_type, omit it — do not fabricate a placeholder. "
    "Output strict JSON matching the provided schema and nothing else."
)

_RESPONSE_SCHEMA: Final[dict[str, object]] = {
    "type": "OBJECT",
    "properties": {
        "facts": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "evidence_type": {"type": "STRING", "enum": list(EVIDENCE_TYPES)},
                    "value": {"type": "STRING"},
                    "page_number": {"type": "INTEGER"},
                    "confidence": {"type": "NUMBER"},
                },
                "required": ["evidence_type", "value", "page_number", "confidence"],
            },
        }
    },
    "required": ["facts"],
}


class GeminiExtractionProvider(ExtractionProvider):
    """
    ``ExtractionProvider`` backed by a single Gemini structured-output call
    over already-OCR'd text.

    Args:
        api_key:           Gemini AI Studio API key.
        model:              Model id (default ``"gemini-2.5-flash"``).
        base_url:           Generative Language API base URL.
        temperature:        Sampling temperature (default ``0.0``).
        max_output_tokens:  Response token budget.
        timeout_seconds:    Per-request HTTP timeout.
        max_retries:        Retries for transient failures (429/5xx/timeouts).
        client:             Optional pre-built ``httpx.Client`` (tests).
        sleep:              Injectable sleep function (tests).
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-2.5-flash",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        temperature: float = 0.0,
        max_output_tokens: int = 4096,
        timeout_seconds: float = 30.0,
        max_retries: int = 4,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._http = GeminiHttpClient(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            client=client,
            sleep=sleep,
        )

    def version(self) -> str:
        return f"gemini-extraction:{self._model}"

    def extract_evidence(
        self,
        ocr_result: OCRResult,
        document_id: str,
    ) -> list[EvidenceAttributes]:
        page_marked_text = "\n\n".join(
            f"--- PAGE {page.page_number} ---\n{page.text}" for page in ocr_result.pages
        )
        parts: list[dict[str, object]] = [{"text": page_marked_text}]

        body = self._http.generate_content(
            provider_name=_PROVIDER_NAME,
            parts=parts,
            system_instruction=_SYSTEM_INSTRUCTION,
            temperature=self._temperature,
            max_output_tokens=self._max_output_tokens,
            response_mime_type="application/json",
            response_schema=_RESPONSE_SCHEMA,
        )
        text = self._http.extract_text(body, provider_name=_PROVIDER_NAME)
        facts = _parse_facts_json(text)

        version = self.version()
        now = datetime.now(UTC)
        extracted: list[EvidenceAttributes] = []
        for evidence_type, value, page_number, confidence in facts:
            location = FieldLocation(page_number=page_number, field_name=evidence_type.lower())
            extracted.append(
                make_evidence_attributes(
                    field_name=evidence_type.lower(),
                    field_value=value,
                    document_id=document_id,
                    source_document_ref=ocr_result.document_ref,
                    page_number=page_number,
                    field_location=location,
                    extraction_confidence=confidence,
                    extraction_method=_EXTRACTION_METHOD,
                    extraction_version=version,
                    extracted_at=now,
                )
            )
        return extracted

    def close(self) -> None:
        """Close the underlying HTTP client (called on process shutdown)."""
        self._http.close()


def _parse_facts_json(text: str) -> list[tuple[str, str, int, float]]:
    """
    Parse the structured-output JSON into validated
    ``(evidence_type, value, page_number, confidence)`` tuples.

    Malformed or out-of-taxonomy/out-of-range entries are dropped rather than
    raising — a partially-usable extraction is preferable to failing the whole
    document on one bad entry, and every dropped entry still leaves the
    document extractable from its other facts. A response that fails to parse
    as JSON at all is a terminal (``retryable=False``) contract violation.
    """
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderError(
            "Gemini extraction response was not valid JSON",
            provider_name=_PROVIDER_NAME,
            retryable=False,
        ) from exc

    raw_facts = parsed.get("facts") if isinstance(parsed, dict) else None
    if not isinstance(raw_facts, list):
        raise ProviderError(
            "Gemini extraction response JSON did not contain a 'facts' array",
            provider_name=_PROVIDER_NAME,
            retryable=False,
        )

    facts: list[tuple[str, str, int, float]] = []
    for entry in raw_facts:
        if not isinstance(entry, dict):
            continue
        evidence_type = entry.get("evidence_type")
        value = entry.get("value")
        page_number = entry.get("page_number")
        confidence = entry.get("confidence")
        if (
            evidence_type not in EVIDENCE_TYPES
            or not isinstance(value, str)
            or not value
            or not isinstance(page_number, int)
            or page_number < 1
            or not isinstance(confidence, (int, float))
        ):
            continue
        clamped_confidence = max(0.0, min(1.0, float(confidence)))
        facts.append((str(evidence_type), value, page_number, clamped_confidence))
    return facts
