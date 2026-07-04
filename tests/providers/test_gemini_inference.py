"""
GeminiInferenceProvider abstraction tests.

These replace the old mock-inference tests (the ``MockInferenceProvider`` was
removed). They verify the *real* provider's behaviour against a deterministic
in-memory ``httpx.MockTransport`` — no network, no real Gemini key — covering:

- the ``InferenceProvider`` contract and Principle XII attribution,
- request shape (endpoint, model, generation config, secret handling),
- grounding rendering and citation scoping,
- robust retry with exponential backoff (429 / 503 / timeouts), and
- terminal (non-retryable) error classification.

The generic interface-conformance suite lives in
``test_inference_conformance.py`` and also now runs against this provider.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest

from mil.kernel.errors import ProviderError
from mil.kernel.providers.inference import GroundingItem, InferenceContext
from providers.inference.gemini_inference import (
    _DEFAULT_SYSTEM_PROMPT,
    GeminiInferenceProvider,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok_body(text: str = "Answer grounded in [ev-001].") -> dict[str, object]:
    return {
        "candidates": [
            {
                "content": {"parts": [{"text": text}], "role": "model"},
                "finishReason": "STOP",
            }
        ]
    }


def _make_provider(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    sleeps: list[float] | None = None,
    max_retries: int = 4,
    model: str = "gemini-2.5-flash",
) -> GeminiInferenceProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    recorded = sleeps if sleeps is not None else []
    return GeminiInferenceProvider(
        api_key="test-api-key",
        model=model,
        max_retries=max_retries,
        client=client,
        sleep=recorded.append,
    )


def _context(
    *,
    query: str = "Is the income consistent?",
    prompt_version: str = "explain-finding-v1",
    grounding: tuple[GroundingItem, ...] = (),
    temperature: float = 0.0,
    max_tokens: int = 1024,
    system_prompt: str | None = None,
) -> InferenceContext:
    if not grounding:
        grounding = (
            GroundingItem(
                kind="EVIDENCE",
                ref="ev-001",
                summary="gross_monthly_income: 5000.00",
                provenance="doc-001#page=1",
                confidence=0.85,
            ),
            GroundingItem(
                kind="FINDING",
                ref="fnd-001",
                summary="Income verification: consistent",
            ),
        )
    return InferenceContext(
        application_id="app-001",
        query=query,
        prompt_version=prompt_version,
        grounding_items=grounding,
        temperature=temperature,
        max_tokens=max_tokens,
        system_prompt=system_prompt,
    )


# ---------------------------------------------------------------------------
# Contract & attribution
# ---------------------------------------------------------------------------


class TestContractAndAttribution:
    def test_version_is_model_scoped(self) -> None:
        provider = _make_provider(lambda _r: httpx.Response(200, json=_ok_body()))
        assert provider.version() == "gemini:gemini-2.5-flash"

    def test_infer_returns_attributed_result(self) -> None:
        provider = _make_provider(lambda _r: httpx.Response(200, json=_ok_body()))
        result = provider.infer(_context(prompt_version="freeform-question-v1"))
        assert result.content == "Answer grounded in [ev-001]."
        assert result.model_version == provider.version()
        assert result.prompt_version == "freeform-question-v1"
        assert result.inference_latency_ms >= 0.0

    def test_empty_api_key_rejected(self) -> None:
        with pytest.raises(ValueError, match="api_key"):
            GeminiInferenceProvider(api_key="")


# ---------------------------------------------------------------------------
# Request shape & secret handling
# ---------------------------------------------------------------------------


class TestRequestShape:
    def _capture(self) -> tuple[list[httpx.Request], Callable[[httpx.Request], httpx.Response]]:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json=_ok_body())

        return seen, handler

    def test_targets_generatecontent_endpoint_with_model(self) -> None:
        seen, handler = self._capture()
        _make_provider(handler).infer(_context())
        assert seen[0].url.path.endswith("/models/gemini-2.5-flash:generateContent")

    def test_api_key_sent_in_header_not_url(self) -> None:
        seen, handler = self._capture()
        _make_provider(handler).infer(_context())
        assert seen[0].headers["x-goog-api-key"] == "test-api-key"
        assert "test-api-key" not in str(seen[0].url)

    def test_temperature_and_max_tokens_forwarded(self) -> None:
        seen, handler = self._capture()
        _make_provider(handler).infer(_context(temperature=0.3, max_tokens=256))
        body = json.loads(seen[0].content)
        assert body["generationConfig"]["temperature"] == 0.3
        assert body["generationConfig"]["maxOutputTokens"] == 256

    def test_default_system_prompt_applied(self) -> None:
        seen, handler = self._capture()
        _make_provider(handler).infer(_context(system_prompt=None))
        body = json.loads(seen[0].content)
        assert body["systemInstruction"]["parts"][0]["text"] == _DEFAULT_SYSTEM_PROMPT

    def test_system_prompt_override_used(self) -> None:
        seen, handler = self._capture()
        _make_provider(handler).infer(_context(system_prompt="Custom governed instruction."))
        body = json.loads(seen[0].content)
        assert body["systemInstruction"]["parts"][0]["text"] == "Custom governed instruction."

    def test_grounding_and_query_rendered_into_user_turn(self) -> None:
        seen, handler = self._capture()
        _make_provider(handler).infer(_context(query="What is the income?"))
        body = json.loads(seen[0].content)
        user_text = body["contents"][0]["parts"][0]["text"]
        assert "[ev-001]" in user_text
        assert "gross_monthly_income: 5000.00" in user_text
        assert "What is the income?" in user_text


# ---------------------------------------------------------------------------
# Citation scoping
# ---------------------------------------------------------------------------


class TestCitationScoping:
    def test_only_echoed_grounding_refs_are_cited(self) -> None:
        # Model echoes ev-001 (present) and ev-999 (NOT in grounding).
        provider = _make_provider(
            lambda _r: httpx.Response(200, json=_ok_body("See [ev-001] and [ev-999]."))
        )
        result = provider.infer(_context())
        assert result.evidence_citations == ("ev-001",)

    def test_no_citations_when_model_cites_nothing(self) -> None:
        provider = _make_provider(
            lambda _r: httpx.Response(200, json=_ok_body("No supporting records were found."))
        )
        result = provider.infer(_context())
        assert result.evidence_citations == ()


# ---------------------------------------------------------------------------
# Retry / backoff
# ---------------------------------------------------------------------------


class _Script:
    """A handler that returns a scripted sequence of responses/exceptions."""

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


class TestRetry:
    def test_retries_on_429_then_succeeds(self) -> None:
        script = _Script(
            [httpx.Response(429), httpx.Response(429), httpx.Response(200, json=_ok_body())]
        )
        sleeps: list[float] = []
        result = _make_provider(script, sleeps=sleeps).infer(_context())
        assert script.calls == 3
        assert len(sleeps) == 2  # slept before each of the two retries
        assert result.content == "Answer grounded in [ev-001]."

    def test_retries_on_503_then_succeeds(self) -> None:
        script = _Script([httpx.Response(503), httpx.Response(200, json=_ok_body())])
        result = _make_provider(script).infer(_context())
        assert script.calls == 2
        assert result.content

    def test_retries_on_timeout_then_succeeds(self) -> None:
        script = _Script([httpx.ConnectTimeout("timed out"), httpx.Response(200, json=_ok_body())])
        result = _make_provider(script).infer(_context())
        assert script.calls == 2
        assert result.content

    def test_honours_retry_after_header(self) -> None:
        script = _Script(
            [
                httpx.Response(429, headers={"Retry-After": "7"}),
                httpx.Response(200, json=_ok_body()),
            ]
        )
        sleeps: list[float] = []
        _make_provider(script, sleeps=sleeps).infer(_context())
        assert sleeps == [7.0]

    def test_exhausts_retries_raises_retryable_error(self) -> None:
        script = _Script([httpx.Response(503)])
        provider = _make_provider(script, max_retries=2)
        with pytest.raises(ProviderError) as excinfo:
            provider.infer(_context())
        assert excinfo.value.retryable is True
        assert script.calls == 3  # 1 initial + 2 retries

    def test_persistent_timeout_raises_retryable_error(self) -> None:
        script = _Script([httpx.ConnectTimeout("nope")])
        provider = _make_provider(script, max_retries=1)
        with pytest.raises(ProviderError) as excinfo:
            provider.infer(_context())
        assert excinfo.value.retryable is True
        assert script.calls == 2


# ---------------------------------------------------------------------------
# Terminal (non-retryable) errors
# ---------------------------------------------------------------------------


class TestTerminalErrors:
    @pytest.mark.parametrize("status", [400, 401, 403, 404])
    def test_client_errors_are_not_retried(self, status: int) -> None:
        script = _Script([httpx.Response(status, json={"error": {"message": "bad"}})])
        provider = _make_provider(script, max_retries=3)
        with pytest.raises(ProviderError) as excinfo:
            provider.infer(_context())
        assert excinfo.value.retryable is False
        assert script.calls == 1  # never retried

    def test_blocked_prompt_raises_terminal(self) -> None:
        provider = _make_provider(
            lambda _r: httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})
        )
        with pytest.raises(ProviderError) as excinfo:
            provider.infer(_context())
        assert excinfo.value.retryable is False

    def test_no_candidates_raises_terminal(self) -> None:
        provider = _make_provider(lambda _r: httpx.Response(200, json={"candidates": []}))
        with pytest.raises(ProviderError) as excinfo:
            provider.infer(_context())
        assert excinfo.value.retryable is False

    def test_empty_text_candidate_raises_terminal(self) -> None:
        provider = _make_provider(
            lambda _r: httpx.Response(
                200,
                json={"candidates": [{"content": {"parts": []}, "finishReason": "MAX_TOKENS"}]},
            )
        )
        with pytest.raises(ProviderError) as excinfo:
            provider.infer(_context())
        assert excinfo.value.retryable is False
