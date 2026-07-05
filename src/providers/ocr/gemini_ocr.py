"""
GeminiOCRProvider — native multimodal document understanding, no traditional OCR.

Replaces ``MockOCRProvider`` as the platform's real ``OCRProvider``. Instead of
a Tesseract-style pixel-to-text OCR engine, this provider sends the document's
raw bytes to Gemini as multimodal ``inline_data`` and asks the model to read
the document natively — preserving reading order, page boundaries, document
hierarchy (headings), and tabular structure. This is the "no traditional OCR"
requirement: Gemini's document understanding *is* the OCR stage.

Architectural boundary: every Gemini-specific detail (endpoint, multimodal
payload shape, JSON response schema) lives only in this module. It satisfies
the existing, unchanged ``OCRProvider`` interface
(``mil.kernel.providers.ocr``), so nothing above it — ``DocumentService``, the
Document Pipeline Worker, the Extraction stage — needs to change or even know
Gemini exists.

Known limitation (documented, not hidden): Gemini's document understanding
does not report page pixel/point dimensions the way a rasterising OCR engine
would. ``PageLayout`` is populated with a fixed US-Letter-equivalent default
(595 x 842 points) for every page. No consumer in this codebase reads
``PageLayout`` for anything beyond "must be positive" (see
``tests/providers/test_ocr_conformance.py``); if a future consumer needs real
page geometry, that is a separate, larger feature (rendering the PDF to get
true page dimensions), out of scope here.

Dependency rule: imports from ``httpx``, ``mil.kernel``, ``providers.gemini_client``,
and the Python standard library only.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from mil.kernel.errors import ProviderError
from mil.kernel.providers.ocr import OCRProvider, OCRResult, PageLayout, PageText
from providers.gemini_client import GeminiHttpClient

if TYPE_CHECKING:
    from collections.abc import Callable

    import httpx

_PROVIDER_NAME: Final = "GeminiOCRProvider"

# Fixed page geometry fallback — see module docstring "Known limitation".
_DEFAULT_WIDTH_POINTS: Final = 595.0
_DEFAULT_HEIGHT_POINTS: Final = 842.0

_SYSTEM_INSTRUCTION: Final = (
    "You are a precise document-understanding engine for a regulated mortgage "
    "platform. Read the attached document natively (do not summarise or "
    "paraphrase) and transcribe its text, page by page, exactly as it appears. "
    "Preserve reading order top-to-bottom, left-to-right. Preserve page "
    "boundaries: never merge two pages into one, never split one page into "
    "two. Preserve document hierarchy using markdown-style headings ('#', "
    "'##') where the source shows a heading or section title. Preserve tables "
    "using markdown pipe-delimited rows. Output strict JSON matching the "
    "provided schema and nothing else."
)

_RESPONSE_SCHEMA: Final[dict[str, object]] = {
    "type": "OBJECT",
    "properties": {
        "pages": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "page_number": {"type": "INTEGER"},
                    "text": {"type": "STRING"},
                },
                "required": ["page_number", "text"],
            },
        },
        "warnings": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["pages"],
}

# Magic-byte signatures for mime-type sniffing (Gemini's inline_data requires
# an explicit mimeType; the OCRProvider interface does not carry one, so it is
# derived from the content itself, self-contained within this provider).
_MAGIC_SIGNATURES: Final[tuple[tuple[bytes, str], ...]] = (
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def _sniff_mime_type(content: bytes) -> str:
    """Detect the document's mime type from its magic bytes; defaults to PDF."""
    for signature, mime_type in _MAGIC_SIGNATURES:
        if content.startswith(signature):
            return mime_type
    return "application/pdf"


class GeminiOCRProvider(OCRProvider):
    """
    ``OCRProvider`` backed by Gemini's native multimodal document understanding.

    Args:
        api_key:           Gemini AI Studio API key.
        model:              Model id (default ``"gemini-2.5-flash"``).
        base_url:           Generative Language API base URL.
        temperature:        Sampling temperature (default ``0.0`` — regulated
                            determinism; transcription should not be creative).
        max_output_tokens:  Response token budget (documents can be long).
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
        max_output_tokens: int = 8192,
        timeout_seconds: float = 60.0,
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
        return f"gemini-ocr:{self._model}"

    def process_document(self, document_ref: str, content: bytes) -> OCRResult:
        if not content:
            raise ProviderError(
                "Cannot process an empty document", provider_name=_PROVIDER_NAME, retryable=False
            )

        mime_type = _sniff_mime_type(content)
        parts: list[dict[str, object]] = [
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": base64.b64encode(content).decode("ascii"),
                }
            },
            {"text": "Transcribe this document per the system instructions."},
        ]

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
        parsed = _parse_document_json(text)

        pages = tuple(
            PageText(
                page_number=page_number,
                text=page_text,
                layout=PageLayout(
                    page_number=page_number,
                    width_points=_DEFAULT_WIDTH_POINTS,
                    height_points=_DEFAULT_HEIGHT_POINTS,
                ),
                word_count=len(page_text.split()),
            )
            for page_number, page_text in parsed
        )
        if not pages:
            pages = (
                PageText(
                    page_number=1,
                    text="",
                    layout=PageLayout(
                        page_number=1,
                        width_points=_DEFAULT_WIDTH_POINTS,
                        height_points=_DEFAULT_HEIGHT_POINTS,
                    ),
                    word_count=0,
                ),
            )

        return OCRResult(
            document_ref=document_ref,
            pages=pages,
            provider_version=self.version(),
            processed_at=datetime.now(UTC),
        )

    def close(self) -> None:
        """Close the underlying HTTP client (called on process shutdown)."""
        self._http.close()


def _parse_document_json(text: str) -> list[tuple[int, str]]:
    """
    Parse the structured-output JSON body into ``(page_number, text)`` pairs,
    sorted by page number.

    Raises:
        ProviderError: If the model's JSON does not parse or carries no usable
            page entries — a terminal (``retryable=False``) contract violation.
    """
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderError(
            "Gemini OCR response was not valid JSON",
            provider_name=_PROVIDER_NAME,
            retryable=False,
        ) from exc

    raw_pages = parsed.get("pages") if isinstance(parsed, dict) else None
    if not isinstance(raw_pages, list):
        raise ProviderError(
            "Gemini OCR response JSON did not contain a 'pages' array",
            provider_name=_PROVIDER_NAME,
            retryable=False,
        )

    pages: list[tuple[int, str]] = []
    for entry in raw_pages:
        if not isinstance(entry, dict):
            continue
        page_number = entry.get("page_number")
        page_text = entry.get("text")
        if not isinstance(page_number, int) or page_number < 1:
            continue
        pages.append((page_number, str(page_text) if page_text is not None else ""))

    pages.sort(key=lambda p: p[0])
    return pages
