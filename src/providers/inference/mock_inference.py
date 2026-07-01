"""
MockInferenceProvider — development inference provider.

Returns deterministic ``InferenceResult`` objects with model version and
prompt version attribution populated.  Intended for local development,
unit tests, and conformance test verification.

MUST NOT be registered in staging or production containers.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from mil.kernel.providers.inference import InferenceProvider, InferenceResult

if TYPE_CHECKING:
    from mil.kernel.providers.inference import InferenceContext

_VERSION = "mock-inference-1.0.0"

_DEFAULT_RESPONSE = (
    "Based on the provided evidence, the extracted income figure is consistent "
    "with the declared monthly income.  No anomalies detected in the reviewed "
    "evidence items.  Recommend verification of the year-to-date gross figure "
    "against the employer payroll records."
)


class MockInferenceProvider(InferenceProvider):
    """
    Deterministic inference provider for development and testing.

    Returns a fixed response for all queries.  The ``model_version`` is
    ``"mock-inference-1.0.0"``.  The ``prompt_version`` is echoed from the
    incoming ``InferenceContext`` to satisfy Principle XII.

    The ``evidence_citations`` in the result contain the ``ref`` values of up
    to three grounding items from the context so that callers receive a
    non-empty citation list.  (Legacy ``evidence_items`` are normalised into
    ``grounding_items`` by ``InferenceContext``, so this works unchanged for
    evidence-only callers.)

    Configurable responses:

    Pass a ``responses`` dict to map exact query strings to custom responses.
    Useful in unit tests that need deterministic per-query behaviour::

        provider = MockInferenceProvider(responses={"income?": "Income looks fine."})
        result = provider.infer(context)  # context.query == "income?"
        assert result.content == "Income looks fine."
    """

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self._responses: dict[str, str] = responses or {}

    def infer(self, context: InferenceContext) -> InferenceResult:
        start = time.monotonic()

        content = self._responses.get(context.query, _DEFAULT_RESPONSE)

        citations = tuple(item.ref for item in context.grounding_items[:3])

        elapsed_ms = (time.monotonic() - start) * 1000.0

        return InferenceResult(
            content=content,
            model_version=_VERSION,
            prompt_version=context.prompt_version,
            evidence_citations=citations,
            inference_latency_ms=elapsed_ms,
        )

    def version(self) -> str:
        return _VERSION
