"""
GeminiExtractionProvider abstraction tests.

Verifies the real ``ExtractionProvider`` implementation's behaviour against a
deterministic in-memory ``httpx.MockTransport`` — no network, no real Gemini
key — covering: request shape (page-marked text, schema-constrained taxonomy),
provenance mapping, malformed-entry filtering, retry/backoff, and terminal
error classification. The generic interface-conformance suite lives in
``test_extraction_conformance.py`` and also runs against this provider.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx
import pytest

from mil.kernel.errors import ProviderError
from mil.kernel.providers.ocr import OCRResult, PageLayout, PageText
from providers.extraction.gemini_extraction import EVIDENCE_TYPES, GeminiExtractionProvider

if TYPE_CHECKING:
    from collections.abc import Callable


def _ocr_result() -> OCRResult:
    layout = PageLayout(page_number=1, width_points=595.0, height_points=842.0)
    return OCRResult(
        document_ref="doc-ref-001",
        pages=(
            PageText(page_number=1, text="Borrower: Jane Doe\nLoan Amount: 350000", layout=layout),
        ),
        provider_version="gemini-ocr:gemini-2.5-flash",
        processed_at=datetime.now(UTC),
    )


def _ok_body(facts: list[dict[str, object]]) -> dict[str, object]:
    return {
        "candidates": [
            {
                "content": {"parts": [{"text": json.dumps({"facts": facts})}], "role": "model"},
                "finishReason": "STOP",
            }
        ]
    }


def _make_provider(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    sleeps: list[float] | None = None,
    max_retries: int = 4,
) -> GeminiExtractionProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    recorded = sleeps if sleeps is not None else []
    return GeminiExtractionProvider(
        api_key="test-api-key", max_retries=max_retries, client=client, sleep=recorded.append
    )


class _Script:
    def __init__(self, steps: list[object]) -> None:
        self._steps = steps
        self.calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        step = self._steps[min(self.calls, len(self._steps) - 1)]
        self.calls += 1
        if isinstance(step, Exception):
            raise step
        assert isinstance(step, httpx.Response)
        return step


_ONE_FACT = [
    {"evidence_type": "BORROWER_NAME", "value": "Jane Doe", "page_number": 1, "confidence": 0.95}
]


class TestRequestShape:
    def _capture(self) -> tuple[list[httpx.Request], Callable[[httpx.Request], httpx.Response]]:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json=_ok_body(_ONE_FACT))

        return seen, handler

    def test_sends_page_marked_text(self) -> None:
        seen, handler = self._capture()
        _make_provider(handler).extract_evidence(_ocr_result(), "doc-1")
        body = json.loads(seen[0].content)
        text = body["contents"][0]["parts"][0]["text"]
        assert "--- PAGE 1 ---" in text
        assert "Borrower: Jane Doe" in text

    def test_no_multimodal_parts_text_only(self) -> None:
        seen, handler = self._capture()
        _make_provider(handler).extract_evidence(_ocr_result(), "doc-1")
        body = json.loads(seen[0].content)
        assert "inline_data" not in body["contents"][0]["parts"][0]

    def test_schema_constrains_evidence_type_enum(self) -> None:
        seen, handler = self._capture()
        _make_provider(handler).extract_evidence(_ocr_result(), "doc-1")
        body = json.loads(seen[0].content)
        schema = body["generationConfig"]["responseSchema"]
        enum_values = schema["properties"]["facts"]["items"]["properties"]["evidence_type"]["enum"]
        assert set(enum_values) == set(EVIDENCE_TYPES)

    def test_api_key_sent_in_header_not_url(self) -> None:
        seen, handler = self._capture()
        _make_provider(handler).extract_evidence(_ocr_result(), "doc-1")
        assert seen[0].headers["x-goog-api-key"] == "test-api-key"
        assert "test-api-key" not in str(seen[0].url)


class TestResultMapping:
    def test_version_is_model_scoped(self) -> None:
        provider = _make_provider(lambda _r: httpx.Response(200, json=_ok_body(_ONE_FACT)))
        assert provider.version() == "gemini-extraction:gemini-2.5-flash"

    def test_maps_fact_to_evidence_attributes(self) -> None:
        provider = _make_provider(lambda _r: httpx.Response(200, json=_ok_body(_ONE_FACT)))
        result = provider.extract_evidence(_ocr_result(), "doc-1")
        assert len(result) == 1
        item = result[0]
        assert item.field_name == "borrower_name"
        assert item.field_value == "Jane Doe"
        assert item.document_id == "doc-1"
        assert item.source_document_ref == "doc-ref-001"
        assert item.page_number == 1
        assert item.extraction_confidence == 0.95
        assert item.extraction_version == provider.version()
        assert item.provenance_complete()

    def test_multiple_facts_all_mapped(self) -> None:
        facts = [
            {
                "evidence_type": "BORROWER_NAME",
                "value": "Jane Doe",
                "page_number": 1,
                "confidence": 0.9,
            },
            {
                "evidence_type": "LOAN_AMOUNT",
                "value": "350000",
                "page_number": 1,
                "confidence": 0.8,
            },
        ]
        provider = _make_provider(lambda _r: httpx.Response(200, json=_ok_body(facts)))
        result = provider.extract_evidence(_ocr_result(), "doc-1")
        assert {item.field_name for item in result} == {"borrower_name", "loan_amount"}

    def test_confidence_clamped_to_valid_range(self) -> None:
        facts = [
            {
                "evidence_type": "BORROWER_NAME",
                "value": "Jane Doe",
                "page_number": 1,
                "confidence": 1.5,
            }
        ]
        provider = _make_provider(lambda _r: httpx.Response(200, json=_ok_body(facts)))
        result = provider.extract_evidence(_ocr_result(), "doc-1")
        assert result[0].extraction_confidence == 1.0

    def test_out_of_taxonomy_evidence_type_is_dropped(self) -> None:
        facts = [
            {"evidence_type": "NOT_A_REAL_TYPE", "value": "x", "page_number": 1, "confidence": 0.9},
            *_ONE_FACT,
        ]
        provider = _make_provider(lambda _r: httpx.Response(200, json=_ok_body(facts)))
        result = provider.extract_evidence(_ocr_result(), "doc-1")
        assert len(result) == 1
        assert result[0].field_name == "borrower_name"

    def test_missing_required_field_is_dropped(self) -> None:
        facts = [{"evidence_type": "BORROWER_NAME", "value": "Jane Doe"}, *_ONE_FACT]
        provider = _make_provider(lambda _r: httpx.Response(200, json=_ok_body(facts)))
        result = provider.extract_evidence(_ocr_result(), "doc-1")
        assert len(result) == 1

    def test_empty_facts_returns_empty_list(self) -> None:
        provider = _make_provider(lambda _r: httpx.Response(200, json=_ok_body([])))
        result = provider.extract_evidence(_ocr_result(), "doc-1")
        assert result == []


class TestRetryAndErrors:
    def test_retries_on_429_then_succeeds(self) -> None:
        script = _Script([httpx.Response(429), httpx.Response(200, json=_ok_body(_ONE_FACT))])
        result = _make_provider(script).extract_evidence(_ocr_result(), "doc-1")
        assert script.calls == 2
        assert len(result) == 1

    def test_exhausts_retries_raises_retryable_error(self) -> None:
        script = _Script([httpx.Response(503)])
        provider = _make_provider(script, max_retries=1)
        with pytest.raises(ProviderError) as excinfo:
            provider.extract_evidence(_ocr_result(), "doc-1")
        assert excinfo.value.retryable is True
        assert script.calls == 2

    def test_client_error_is_terminal(self) -> None:
        script = _Script([httpx.Response(401, json={"error": {"message": "unauthorized"}})])
        provider = _make_provider(script, max_retries=3)
        with pytest.raises(ProviderError) as excinfo:
            provider.extract_evidence(_ocr_result(), "doc-1")
        assert excinfo.value.retryable is False
        assert script.calls == 1

    def test_invalid_json_response_is_terminal(self) -> None:
        provider = _make_provider(
            lambda _r: httpx.Response(
                200,
                json={
                    "candidates": [
                        {"content": {"parts": [{"text": "not json"}]}, "finishReason": "STOP"}
                    ]
                },
            )
        )
        with pytest.raises(ProviderError) as excinfo:
            provider.extract_evidence(_ocr_result(), "doc-1")
        assert excinfo.value.retryable is False
