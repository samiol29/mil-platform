"""
GeminiOCRProvider abstraction tests.

Verifies the real ``OCRProvider`` implementation's behaviour against a
deterministic in-memory ``httpx.MockTransport`` — no network, no real Gemini
key — covering: multimodal request shape (inline_data + mime sniffing),
page-boundary/JSON-schema parsing, retry/backoff, and terminal error
classification. The generic interface-conformance suite lives in
``test_ocr_conformance.py`` and also runs against this provider.
"""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING

import httpx
import pytest

from mil.kernel.errors import ProviderError
from providers.ocr.gemini_ocr import GeminiOCRProvider, _sniff_mime_type

if TYPE_CHECKING:
    from collections.abc import Callable

_PDF_BYTES = b"%PDF-1.4 minimal pdf content for testing"


def _ok_body(pages: list[dict[str, object]]) -> dict[str, object]:
    return {
        "candidates": [
            {
                "content": {"parts": [{"text": json.dumps({"pages": pages})}], "role": "model"},
                "finishReason": "STOP",
            }
        ]
    }


def _make_provider(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    sleeps: list[float] | None = None,
    max_retries: int = 4,
) -> GeminiOCRProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    recorded = sleeps if sleeps is not None else []
    return GeminiOCRProvider(
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


class TestMimeSniffing:
    def test_pdf_magic_bytes(self) -> None:
        assert _sniff_mime_type(b"%PDF-1.4 rest") == "application/pdf"

    def test_png_magic_bytes(self) -> None:
        assert _sniff_mime_type(b"\x89PNG\r\n\x1a\n rest") == "image/png"

    def test_jpeg_magic_bytes(self) -> None:
        assert _sniff_mime_type(b"\xff\xd8\xff rest") == "image/jpeg"

    def test_unknown_defaults_to_pdf(self) -> None:
        assert _sniff_mime_type(b"not a real document") == "application/pdf"


class TestRequestShape:
    def _capture(self) -> tuple[list[httpx.Request], Callable[[httpx.Request], httpx.Response]]:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json=_ok_body([{"page_number": 1, "text": "hello"}]))

        return seen, handler

    def test_sends_inline_data_with_sniffed_mime_type(self) -> None:
        seen, handler = self._capture()
        _make_provider(handler).process_document("doc-ref", _PDF_BYTES)
        body = json.loads(seen[0].content)
        inline = body["contents"][0]["parts"][0]["inline_data"]
        assert inline["mime_type"] == "application/pdf"
        assert base64.b64decode(inline["data"]) == _PDF_BYTES

    def test_api_key_sent_in_header_not_url(self) -> None:
        seen, handler = self._capture()
        _make_provider(handler).process_document("doc-ref", _PDF_BYTES)
        assert seen[0].headers["x-goog-api-key"] == "test-api-key"
        assert "test-api-key" not in str(seen[0].url)

    def test_requests_json_response_schema(self) -> None:
        seen, handler = self._capture()
        _make_provider(handler).process_document("doc-ref", _PDF_BYTES)
        body = json.loads(seen[0].content)
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert "responseSchema" in body["generationConfig"]


class TestResultParsing:
    def test_pages_parsed_in_order(self) -> None:
        provider = _make_provider(
            lambda _r: httpx.Response(
                200,
                json=_ok_body(
                    [
                        {"page_number": 2, "text": "second"},
                        {"page_number": 1, "text": "first"},
                    ]
                ),
            )
        )
        result = provider.process_document("doc-ref", _PDF_BYTES)
        assert [p.page_number for p in result.pages] == [1, 2]
        assert result.pages[0].text == "first"

    def test_document_ref_echoed(self) -> None:
        provider = _make_provider(
            lambda _r: httpx.Response(200, json=_ok_body([{"page_number": 1, "text": "x"}]))
        )
        result = provider.process_document("s3://bucket/doc.pdf", _PDF_BYTES)
        assert result.document_ref == "s3://bucket/doc.pdf"

    def test_version_is_model_scoped(self) -> None:
        provider = _make_provider(lambda _r: httpx.Response(200, json=_ok_body([])))
        assert provider.version() == "gemini-ocr:gemini-2.5-flash"

    def test_empty_content_raises_terminal(self) -> None:
        provider = _make_provider(lambda _r: httpx.Response(200, json=_ok_body([])))
        with pytest.raises(ProviderError) as excinfo:
            provider.process_document("doc-ref", b"")
        assert excinfo.value.retryable is False


class TestRetryAndErrors:
    def test_retries_on_503_then_succeeds(self) -> None:
        script = _Script(
            [
                httpx.Response(503),
                httpx.Response(200, json=_ok_body([{"page_number": 1, "text": "ok"}])),
            ]
        )
        result = _make_provider(script).process_document("doc-ref", _PDF_BYTES)
        assert script.calls == 2
        assert result.pages[0].text == "ok"

    def test_exhausts_retries_raises_retryable_error(self) -> None:
        script = _Script([httpx.Response(503)])
        provider = _make_provider(script, max_retries=1)
        with pytest.raises(ProviderError) as excinfo:
            provider.process_document("doc-ref", _PDF_BYTES)
        assert excinfo.value.retryable is True
        assert script.calls == 2

    def test_client_error_is_terminal(self) -> None:
        script = _Script([httpx.Response(400, json={"error": {"message": "bad request"}})])
        provider = _make_provider(script, max_retries=3)
        with pytest.raises(ProviderError) as excinfo:
            provider.process_document("doc-ref", _PDF_BYTES)
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
            provider.process_document("doc-ref", _PDF_BYTES)
        assert excinfo.value.retryable is False
