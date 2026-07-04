"""
Shared low-level Gemini AI Studio HTTP client — retry/backoff engine.

Every Gemini-backed provider (OCR, Extraction; Inference has its own
self-contained copy, shipped earlier and left untouched) needs the same
plumbing: call ``generateContent`` over ``httpx``, retry transient failures
with exponential backoff and jitter, and turn a response into either parsed
JSON or a terminal ``ProviderError``. Factoring that plumbing here means the
retry engine is written and tested once and reused, rather than re-implemented
per provider (this module has no domain knowledge — it is pure HTTP + retry
machinery for the Generative Language API).

Architectural boundary: this module still lives under ``src/providers/`` — it
is Gemini-specific transport, not business logic. Nothing in ``mil.*`` may
import it; only concrete provider implementations under ``src/providers/``
may.

Dependency rule: imports from ``httpx``, ``mil.kernel.errors``, and the Python
standard library only.
"""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING, Any, Final

import httpx

from mil.kernel.errors import ProviderError

if TYPE_CHECKING:
    from collections.abc import Callable

# HTTP statuses that represent a transient, retryable server-side condition.
_RETRYABLE_STATUS: Final[frozenset[int]] = frozenset({429, 500, 502, 503, 504})


class GeminiHttpClient:
    """
    Reusable Gemini ``generateContent`` caller with retry/backoff.

    Construct one per concrete provider (each provider owns its model, API
    key, and retry budget independently — nothing is shared at the network
    level beyond this class's behaviour).

    Args:
        api_key:           Gemini AI Studio API key.
        model:              Model id, e.g. ``"gemini-2.5-flash"``.
        base_url:           Generative Language API base URL (version-pinned).
        timeout_seconds:    Per-request HTTP timeout.
        max_retries:        Maximum retries after the first attempt for
                            transient failures (429/5xx/timeouts).
        base_backoff:       Base delay (seconds) for exponential backoff.
        max_backoff:        Ceiling (seconds) for a single backoff sleep.
        client:             Optional pre-built ``httpx.Client`` (tests inject
                            one wrapping ``httpx.MockTransport``).
        sleep:              Injectable sleep function (tests pass a no-op).
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: float = 30.0,
        max_retries: int = 4,
        base_backoff: float = 0.5,
        max_backoff: float = 30.0,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key cannot be empty")
        if not model:
            raise ValueError("model cannot be empty")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        self.model = model
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._base_backoff = base_backoff
        self._max_backoff = max_backoff
        self._sleep = sleep if sleep is not None else time.sleep
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            headers={"x-goog-api-key": api_key},
        )
        # Auth header travels only in the header, never the URL (never leaks
        # into access logs or traces). Present even when a client is injected.
        self._client.headers.setdefault("x-goog-api-key", api_key)

    def close(self) -> None:
        """Close the underlying HTTP client (called on process shutdown)."""
        self._client.close()

    def generate_content(
        self,
        *,
        provider_name: str,
        parts: list[dict[str, object]],
        system_instruction: str | None = None,
        temperature: float = 0.0,
        max_output_tokens: int = 2048,
        response_mime_type: str | None = None,
        response_schema: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        """
        Call ``generateContent`` and return the parsed JSON response body.

        Args:
            provider_name:      Name reported in ``ProviderError`` (e.g.
                                ``"GeminiOCRProvider"``) so failures are
                                attributable to the calling provider.
            parts:              The ``contents[0].parts`` list — text and/or
                                ``inline_data`` parts for multimodal input.
            system_instruction: Optional system instruction text.
            temperature:        Sampling temperature.
            max_output_tokens:  Response token budget.
            response_mime_type: When set to ``"application/json"``, Gemini is
                                constrained to emit valid JSON (structured
                                output).
            response_schema:    Optional JSON schema constraining the shape of
                                the JSON response (requires
                                ``response_mime_type="application/json"``).

        Raises:
            ProviderError: Non-retryable API error, or retries exhausted.
        """
        generation_config: dict[str, object] = {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        }
        if response_mime_type is not None:
            generation_config["responseMimeType"] = response_mime_type
        if response_schema is not None:
            generation_config["responseSchema"] = response_schema

        payload: dict[str, object] = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": generation_config,
        }
        if system_instruction is not None:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        url = f"{self._base_url}/models/{self.model}:generateContent"
        response = self._post_with_retry(url, payload, provider_name=provider_name)
        return self._parse_json_body(response, provider_name=provider_name)

    @staticmethod
    def extract_text(body: dict[str, Any], *, provider_name: str) -> str:
        """
        Pull the model's answer text out of a Gemini ``generateContent`` body.

        Raises:
            ProviderError: If the prompt was blocked, no candidate was
                returned, or the candidate carried no text — terminal
                (``retryable=False``), since retrying cannot fix it.
        """
        prompt_feedback = body.get("promptFeedback")
        if isinstance(prompt_feedback, dict) and prompt_feedback.get("blockReason"):
            raise ProviderError(
                f"Gemini blocked the prompt: {prompt_feedback.get('blockReason')}",
                provider_name=provider_name,
                details={"block_reason": str(prompt_feedback.get("blockReason"))},
                retryable=False,
            )

        candidates = body.get("candidates")
        if not candidates:
            raise ProviderError(
                "Gemini returned no candidates", provider_name=provider_name, retryable=False
            )

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        if not text:
            finish_reason = candidates[0].get("finishReason", "UNKNOWN")
            raise ProviderError(
                f"Gemini candidate contained no text (finishReason={finish_reason})",
                provider_name=provider_name,
                details={"finish_reason": str(finish_reason)},
                retryable=False,
            )
        return text

    # ------------------------------------------------------------------
    # HTTP with retry
    # ------------------------------------------------------------------

    def _post_with_retry(
        self, url: str, payload: dict[str, object], *, provider_name: str
    ) -> httpx.Response:
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.post(url, json=payload)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt < self._max_retries:
                    self._sleep(self._backoff_delay(attempt, retry_after=None))
                    continue
                raise ProviderError(
                    f"Gemini request failed after {attempt + 1} attempt(s): {type(exc).__name__}",
                    provider_name=provider_name,
                    retryable=True,
                ) from exc

            if response.status_code == 200:
                return response

            if response.status_code in _RETRYABLE_STATUS and attempt < self._max_retries:
                retry_after = _parse_retry_after(response)
                self._sleep(self._backoff_delay(attempt, retry_after=retry_after))
                continue

            raise self._error_for_status(
                response, attempts=attempt + 1, provider_name=provider_name
            )

        raise ProviderError(
            "Gemini request exhausted all retries without a response",
            provider_name=provider_name,
            retryable=True,
        ) from last_error

    def _backoff_delay(self, attempt: int, *, retry_after: float | None) -> float:
        if retry_after is not None:
            return min(retry_after, self._max_backoff)
        ceiling = min(self._base_backoff * (2**attempt), self._max_backoff)
        return random.uniform(0.0, ceiling)

    @staticmethod
    def _error_for_status(
        response: httpx.Response, *, attempts: int, provider_name: str
    ) -> ProviderError:
        retryable = response.status_code in _RETRYABLE_STATUS
        detail = _safe_error_detail(response)
        return ProviderError(
            f"Gemini API returned HTTP {response.status_code} after {attempts} attempt(s): {detail}",
            provider_name=provider_name,
            details={"status_code": response.status_code},
            retryable=retryable,
        )

    @staticmethod
    def _parse_json_body(response: httpx.Response, *, provider_name: str) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise ProviderError(
                "Gemini returned a non-JSON response body",
                provider_name=provider_name,
                retryable=False,
            ) from exc
        if not isinstance(body, dict):
            raise ProviderError(
                "Gemini returned a JSON body that was not an object",
                provider_name=provider_name,
                retryable=False,
            )
        return body


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Parse a numeric ``Retry-After`` header (seconds); ``None`` if absent/invalid."""
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value >= 0.0 else None


def _safe_error_detail(response: httpx.Response) -> str:
    """Extract a short, safe error message from a Gemini error body; never raises."""
    try:
        body = response.json()
    except ValueError:
        return response.reason_phrase or "unknown error"
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
    return response.reason_phrase or "unknown error"
