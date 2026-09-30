"""
GeminiInferenceProvider — production inference backed by Google Gemini AI Studio.

This is the first *real* ``InferenceProvider`` implementation.  It executes a
grounded inference call against the Google Gemini ``generateContent`` REST
endpoint and returns a structured ``InferenceResult`` carrying model-version
and prompt-version attribution (Engineering Constitution Principle XII —
Deterministic Intelligence).

Architectural boundary
----------------------
Every Gemini-specific detail — the endpoint shape, the request/response JSON,
the authentication header, the retry classification — lives **only** in this
module.  Nothing above the ``InferenceProvider`` interface (``CopilotService``,
the API layer, the finding pipeline) knows that Gemini exists.  Swapping in a
Claude, OpenAI, Azure OpenAI, vLLM, or Ollama provider is a composition-root
change (register a different ``InferenceProvider``) and touches no business
logic (ARCHITECTURE.md §5/§6).

No vendor SDK is used.  Gemini is called over the platform's existing
``httpx`` dependency, so the provider adds no new compile-time dependency and
keeps the "no AI vendor SDK in core" property of ``pyproject.toml`` intact.

Secrets
-------
The provider never reads the environment itself.  The API key is injected by
the composition root (``build_container`` -> ``Settings.gemini_api_key``, read
from ``GEMINI_API_KEY``).  The key is sent in the ``x-goog-api-key`` request
header — never in the URL — so it does not leak into access logs or traces.

Determinism & least-data
------------------------
Temperature defaults to ``0.0`` (most deterministic decoding).  Only the
grounding summaries the caller already scoped into the ``InferenceContext`` are
sent to the model — the provider adds no application data of its own
(Principle V).

Dependency rule: imports from ``httpx``, ``mil.kernel``, and the Python
standard library only.  No bounded context code is imported here.
"""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING, Final

import httpx

from mil.kernel.errors import ProviderError
from mil.kernel.providers.inference import (
    InferenceProvider,
    InferenceResult,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from mil.kernel.providers.inference import GroundingItem, InferenceContext

_PROVIDER_NAME: Final = "GeminiInferenceProvider"

# HTTP statuses that represent a transient, retryable server-side condition.
# 429 (rate limited) and 5xx (server/unavailable) are safe to retry; a 4xx
# other than 429 is a client/contract error that retrying cannot fix.
_RETRYABLE_STATUS: Final[frozenset[int]] = frozenset({429, 500, 502, 503, 504})

# The governed default system instruction, applied when the caller does not
# supply its own ``system_prompt``.  It is deliberately domain-neutral: it
# constrains the model to the supplied grounding and to citing refs, without
# encoding any mortgage-specific semantics (that stays in the Copilot context).
#
# The illustrative reference in the citation instruction below is
# deliberately UUID-shaped, matching what `CopilotService._build_grounding_items`
# actually sends (every real ref is `str(some_uuid)`, e.g.
# `"64cd5379-5104-4758-b443-5f8ea8ab2db6"`) — an earlier version used a
# short fake example (`[ev-001]`), which primed the model to expect a
# short-id citation style it was never actually shown, and to summarize in
# flowing prose without echoing the real (long) reference verbatim. Since
# `_extract_citations` derives citations by an exact substring match of the
# real ref inside the model's answer text, that mismatch meant Gemini's
# answer would very often carry zero recoverable citations — even when real,
# substantive grounding existed — and every such response was silently
# downgraded to the fixed "insufficient grounding" fallback (reproduced live:
# a real "Summarize application" query against an application with real
# evidence/findings/policy results returned `degraded_reason:
# "ungrounded_model_response"`, not a Gemini quota/error condition). Fixed by
# matching the example to the real shape and stating the verbatim-copy
# requirement explicitly, rather than loosening the citation-matching logic
# itself (which would weaken ADR-011's anti-fabrication guarantee).
#
# Second gap, found via live stress-testing a broad question set (grounding-
# pipeline audit sprint): interpretive/analytical questions ("explain the
# underwriting risks", "is there possible fraud", "what is their monthly
# income" — a sum across several EVIDENCE records) came back with zero
# resolved citations and were downgraded to the safe-failure message, even
# though real evidence supported an answer (reproduced live: audit events
# with degraded_reason "ungrounded_model_response" for exactly these three
# questions, on an application with rich EVIDENCE/FINDING grounding for all
# three). Fixed with an explicit instruction covering interpretation/synthesis,
# applied uniformly to every query — not a per-question handler.
_DEFAULT_SYSTEM_PROMPT: Final = (
    "You are a careful evidence assistant for a regulated review platform. "
    "Answer the question using ONLY the grounding records provided. Every "
    "record is labelled with its exact reference in square brackets, e.g. "
    "[3fa85f64-5717-4562-b3fc-2c963f66afa6] — references are long identifiers, "
    "not short labels. Immediately after any claim you make, copy that exact "
    "bracketed reference verbatim (every character, including hyphens) from "
    "the grounding record you relied on — never paraphrase, shorten, or "
    "invent one. This applies even when summarizing broadly: cite the "
    "reference for every record your summary draws on. This also applies to "
    "interpretive or analytical questions — assessing risk, evaluating "
    "possible fraud, computing a total from several figures, or judging "
    "whether documents are consistent are not exceptions: identify the "
    "specific records your interpretation rests on and cite every one of "
    "them, the same as you would for a direct factual lookup. Never offer an "
    "analysis, judgment, or computed total without citing the records it is "
    "based on. If the grounding records do not contain enough information to "
    "answer, say so plainly and do not speculate. Never invent references, "
    "figures, or facts that are not present in the grounding."
)


class GeminiInferenceProvider(InferenceProvider):
    """
    ``InferenceProvider`` backed by the Google Gemini AI Studio REST API.

    Construct with an injected API key and model (both resolved from
    ``Settings`` by the composition root).  The provider owns a single reusable
    ``httpx.Client``; construct it once at startup and register it as a
    singleton (``build_container`` does this).

    Args:
        api_key:           Gemini AI Studio API key (from ``GEMINI_API_KEY``).
        model:             Model id, e.g. ``"gemini-2.5-flash"`` or
                           ``"gemini-2.5-pro"``.
        base_url:          Generative Language API base URL (version-pinned).
        temperature:       Default sampling temperature when a context does not
                           override it via ``InferenceContext.temperature``.
        max_output_tokens: Default response token budget when a context does not
                           override it via ``InferenceContext.max_tokens``.
        timeout_seconds:   Per-request timeout for each HTTP attempt.
        max_retries:       Maximum number of *retries* after the first attempt
                           for transient failures (429/5xx/timeouts).
        base_backoff:      Base delay (seconds) for exponential backoff.
        max_backoff:       Ceiling (seconds) for a single backoff sleep.
        client:            Optional pre-built ``httpx.Client`` (dependency
                           injection for tests — pass one wrapping an
                           ``httpx.MockTransport`` to test without a network).
        sleep:             Injectable sleep function (tests pass a no-op to
                           avoid real delays); defaults to ``time.sleep``.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-2.5-flash",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        temperature: float = 0.0,
        max_output_tokens: int = 1024,
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

        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._default_temperature = temperature
        self._default_max_output_tokens = max_output_tokens
        self._max_retries = max_retries
        self._base_backoff = base_backoff
        self._max_backoff = max_backoff
        self._sleep = sleep if sleep is not None else time.sleep
        # A single reusable client. The API key travels in a header (never the
        # URL) so it does not appear in access logs, traces, or error messages.
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            headers={"x-goog-api-key": api_key},
        )
        # If a client was injected (tests), make sure the auth header is present
        # without overwriting any header the caller deliberately set.
        self._client.headers.setdefault("x-goog-api-key", api_key)

    # ------------------------------------------------------------------
    # InferenceProvider contract
    # ------------------------------------------------------------------

    def version(self) -> str:
        """
        Return the stable model-version identifier for attribution.

        Every ``InferenceResult`` this provider returns carries this exact
        string as its ``model_version`` (Principle XII).  It is derived solely
        from the configured model so it is deterministic and reproducible.
        """
        return f"gemini:{self._model}"

    def infer(self, context: InferenceContext) -> InferenceResult:
        """
        Execute a grounded Gemini inference call for ``context``.

        Builds a Gemini ``generateContent`` request from the scoped grounding
        set, sends it with exponential-backoff retry on transient failures,
        parses the candidate text, and derives citations by resolving grounding
        refs the model echoed back.

        Raises:
            ProviderError: On a non-retryable API error (``retryable=False``)
                or once transient retries are exhausted (``retryable=True``) —
                the ``retryable`` flag lets the orchestrator classify the
                failure without inspecting Gemini internals (ADR-008).
        """
        payload = self._build_payload(context)
        url = f"{self._base_url}/models/{self._model}:generateContent"

        start = time.monotonic()
        response = self._post_with_retry(url, payload)
        elapsed_ms = (time.monotonic() - start) * 1000.0

        content = self._extract_text(response)
        citations = _extract_citations(content, context.grounding_items)

        return InferenceResult(
            content=content,
            model_version=self.version(),
            prompt_version=context.prompt_version,
            evidence_citations=citations,
            inference_latency_ms=elapsed_ms,
        )

    def close(self) -> None:
        """Close the underlying HTTP client (called on process shutdown)."""
        self._client.close()

    # ------------------------------------------------------------------
    # Request construction
    # ------------------------------------------------------------------

    def _build_payload(self, context: InferenceContext) -> dict[str, object]:
        system_prompt = context.system_prompt or _DEFAULT_SYSTEM_PROMPT
        temperature = (
            context.temperature if context.temperature is not None else self._default_temperature
        )
        max_output_tokens = context.max_tokens or self._default_max_output_tokens

        generation_config: dict[str, object] = {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        }
        if context.thinking_budget is not None:
            generation_config["thinkingConfig"] = {"thinkingBudget": context.thinking_budget}

        return {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": _build_user_content(context)}]}],
            "generationConfig": generation_config,
        }

    # ------------------------------------------------------------------
    # HTTP with retry
    # ------------------------------------------------------------------

    def _post_with_retry(self, url: str, payload: dict[str, object]) -> httpx.Response:
        """
        POST ``payload`` to ``url``, retrying transient failures with
        exponential backoff and full jitter.

        Retryable conditions: HTTP 429/500/502/503/504, request timeouts, and
        transport-level connection errors.  Everything else fails immediately
        as a terminal ``ProviderError``.
        """
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.post(url, json=payload)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                # Network-level fault — transient by nature; retry if budget left.
                last_error = exc
                if attempt < self._max_retries:
                    self._sleep(self._backoff_delay(attempt, retry_after=None))
                    continue
                raise ProviderError(
                    f"Gemini request failed after {attempt + 1} attempt(s): {type(exc).__name__}",
                    provider_name=_PROVIDER_NAME,
                    retryable=True,
                ) from exc

            if response.status_code == 200:
                return response

            if response.status_code in _RETRYABLE_STATUS and attempt < self._max_retries:
                retry_after = _parse_retry_after(response)
                self._sleep(self._backoff_delay(attempt, retry_after=retry_after))
                continue

            # Non-retryable, or retries exhausted on a retryable status.
            raise self._error_for_status(response, attempts=attempt + 1)

        # Unreachable: the loop always returns or raises. Present for type
        # completeness and as a defensive guard.
        raise ProviderError(
            "Gemini request exhausted all retries without a response",
            provider_name=_PROVIDER_NAME,
            retryable=True,
        ) from last_error

    def _backoff_delay(self, attempt: int, *, retry_after: float | None) -> float:
        """
        Compute the sleep before the next attempt.

        Honours a server-provided ``Retry-After`` when present; otherwise uses
        exponential backoff (``base * 2**attempt``) with full jitter, capped at
        ``max_backoff``.  Full jitter avoids a synchronised retry stampede
        across concurrent workers.
        """
        if retry_after is not None:
            return min(retry_after, self._max_backoff)
        ceiling = min(self._base_backoff * (2**attempt), self._max_backoff)
        return random.uniform(0.0, ceiling)

    def _error_for_status(self, response: httpx.Response, *, attempts: int) -> ProviderError:
        retryable = response.status_code in _RETRYABLE_STATUS
        detail = _safe_error_detail(response)
        return ProviderError(
            f"Gemini API returned HTTP {response.status_code} after {attempts} attempt(s): {detail}",
            provider_name=_PROVIDER_NAME,
            details={"status_code": response.status_code},
            retryable=retryable,
        )

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _extract_text(self, response: httpx.Response) -> str:
        """
        Pull the model's answer text out of a Gemini ``generateContent`` body.

        Raises:
            ProviderError: If the prompt was blocked, no candidate was
                returned, or the candidate carried no text — none of which are
                fixable by retrying (``retryable=False``).
        """
        try:
            body = response.json()
        except ValueError as exc:
            raise ProviderError(
                "Gemini returned a non-JSON response body",
                provider_name=_PROVIDER_NAME,
                retryable=False,
            ) from exc

        prompt_feedback = body.get("promptFeedback") if isinstance(body, dict) else None
        if isinstance(prompt_feedback, dict) and prompt_feedback.get("blockReason"):
            raise ProviderError(
                f"Gemini blocked the prompt: {prompt_feedback.get('blockReason')}",
                provider_name=_PROVIDER_NAME,
                details={"block_reason": str(prompt_feedback.get("blockReason"))},
                retryable=False,
            )

        candidates = body.get("candidates") if isinstance(body, dict) else None
        if not candidates:
            raise ProviderError(
                "Gemini returned no candidates",
                provider_name=_PROVIDER_NAME,
                retryable=False,
            )

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        if not text:
            finish_reason = candidates[0].get("finishReason", "UNKNOWN")
            raise ProviderError(
                f"Gemini candidate contained no text (finishReason={finish_reason})",
                provider_name=_PROVIDER_NAME,
                details={"finish_reason": str(finish_reason)},
                retryable=False,
            )
        return text


# ---------------------------------------------------------------------------
# Module-level helpers (pure functions — no Gemini state)
# ---------------------------------------------------------------------------


def _build_user_content(context: InferenceContext) -> str:
    """
    Render the scoped grounding set and the query into a single user turn.

    Only the grounding summaries the caller already scoped into the context are
    included — the provider adds no application data of its own (Principle V,
    least-data).
    """
    if context.grounding_items:
        grounding_block = "\n".join(
            _render_grounding_item(item) for item in context.grounding_items
        )
    else:
        grounding_block = "(no grounding records supplied)"
    return f"GROUNDING RECORDS:\n{grounding_block}\n\nQUESTION:\n{context.query}"


def _render_grounding_item(item: GroundingItem) -> str:
    parts = [f"[{item.ref}] ({item.kind}) {item.summary}"]
    if item.provenance:
        parts.append(f"source: {item.provenance}")
    if item.confidence is not None:
        parts.append(f"confidence: {item.confidence:.2f}")
    return " | ".join(parts)


def _extract_citations(content: str, grounding_items: Sequence[GroundingItem]) -> tuple[str, ...]:
    """
    Derive citations by resolving grounding refs the model echoed back.

    A ref is credited only if it belongs to the supplied grounding set AND
    appears in the answer text — the provider can never emit a citation to
    something outside the scoped context (satisfies the conformance
    "citations are a subset of context refs" contract).  ``CopilotService``
    independently re-validates every returned ref against its own grounding
    index (ADR-011 §6), so this is a best-effort attribution, not a trust
    boundary.
    """
    seen: set[str] = set()
    resolved: list[str] = []
    for item in grounding_items:
        if item.ref in seen:
            continue
        if item.ref in content:
            resolved.append(item.ref)
            seen.add(item.ref)
    return tuple(resolved)


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
    """
    Extract a short, safe error message from a Gemini error body.

    Falls back to the reason phrase; never raises, so it is safe to call while
    already constructing an error.
    """
    try:
        body = response.json()
    except ValueError:
        return response.reason_phrase or "unknown error"
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
    return response.reason_phrase or "unknown error"
