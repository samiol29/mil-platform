"""
InferenceProvider interface for the MIL Platform.

Executes prompted inference against a scoped evidence context and returns
structured results carrying model version and prompt version attribution
as required by Engineering Constitution Principle XII (Deterministic Intelligence).

The interface is intentionally domain-agnostic.  Evidence is represented as
structured ``EvidenceEntry`` objects rather than domain ``EvidenceItem`` entities
so that inference providers have no dependency on any bounded context.

This module defines only the abstract interface and its data types.
Concrete implementations live in ``src/providers/inference/`` and are
registered via ``ProviderRegistry.register_inference()``.

Dependency rule: this module imports from the Python standard library only.
No bounded context code should be imported here.
"""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

# ---------------------------------------------------------------------------
# Grounding item — the generalized, domain-agnostic grounding abstraction
# ---------------------------------------------------------------------------

# Legacy bridge discriminator.  This is the ONLY grounding ``kind`` the kernel
# names, and it exists solely to normalise the pre-existing ``EvidenceEntry``
# into a ``GroundingItem`` for backwards compatibility (see
# ``InferenceContext.__post_init__``).  It is NOT a domain taxonomy: the full
# set of grounding kinds (finding, policy result, review action, document, …)
# is owned by the Copilot bounded context, never by the kernel.  ``kind`` on
# ``GroundingItem`` is an opaque string precisely so the kernel stays
# domain-agnostic (ARCHITECTURE.md §4).
_EVIDENCE_KIND = "EVIDENCE"


@dataclasses.dataclass(frozen=True)
class GroundingItem:
    """
    A single, domain-agnostic unit of grounding for an inference call.

    ``GroundingItem`` generalises ``EvidenceEntry`` so that a context can be
    grounded on *any* governed record — evidence, an AI finding, a policy
    result, a review action, a document — without the kernel learning what any
    of those mortgage concepts are.  The ``kind`` field is an **opaque string**
    owned by the consuming bounded context; the kernel never interprets it.

    Attributes:
        kind:        Opaque discriminator supplied by the consumer (e.g. the
                     consumer's own ``"FINDING"`` / ``"POLICY_RESULT"``
                     constant).  The kernel treats it as an unstructured label.
        ref:         Stable citation handle for the underlying record.  A
                     provider that cites this item MUST echo this exact value
                     so the consumer can resolve the citation back to a record.
        summary:     Minimal, reviewer-interpretable text the model may ground
                     on.  Principle V (least-data): only what the query needs.
        provenance:  Optional source locator (e.g. ``"doc-ref#page=1"``)
                     preserving Principle II traceability where applicable.
        confidence:  Optional confidence in ``[0.0, 1.0]`` for items that carry
                     one; ``None`` for items that do not (e.g. a review action).
        attributes:  Optional, string-only bag for kind-specific detail the
                     ``summary`` alone cannot carry.  Kept opaque (str→str) so
                     the kernel remains domain-agnostic.
    """

    kind: str
    ref: str
    summary: str
    provenance: str | None = None
    confidence: float | None = None
    attributes: Mapping[str, str] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("kind cannot be empty")
        if not self.ref:
            raise ValueError("ref cannot be empty")
        if not self.summary:
            raise ValueError("summary cannot be empty")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")


# ---------------------------------------------------------------------------
# Inference context and result data types
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class EvidenceEntry:
    """
    A single evidence item formatted for use in an inference context.

    Represents the minimum information needed to ground an inference query
    in a specific piece of evidence.  The Copilot service constructs these
    from domain ``EvidenceItem`` objects before passing to ``InferenceProvider``.

    Principle V (Least-data): only the attributes required for the specific
    query should be populated.  Surplus personal data MUST NOT be included.
    """

    evidence_ref: str
    field_name: str
    field_value: str
    confidence: float
    source_ref: str
    page_number: int = 0


@dataclasses.dataclass(frozen=True)
class InferenceContext:
    """
    Scoped context for a single inference call.

    The ``grounding_items`` tuple contains only the governed records relevant
    to the specific ``query``, scoped strictly to the ``application_id``.  The
    Copilot grounding layer is responsible for enforcing scope before this
    context is constructed.

    Backwards compatibility: ``evidence_items`` (the original, evidence-only
    field) is retained.  When a caller supplies ``evidence_items`` but no
    ``grounding_items``, the entries are normalised into ``grounding_items`` at
    construction time so that providers can read a single uniform surface
    (``grounding_items``) regardless of which field the caller populated.

    Principle V requirement: both tuples MUST contain only data attributes
    necessary for the requested query.  Prompts MUST NOT carry surplus
    personal data.

    Attributes:
        application_id:  The MIL application ID (for scope enforcement).
        query:           The natural-language query to answer.
        prompt_version:  The version identifier of the prompt template used.
                         Required for Principle XII attribution.
        evidence_items:  Legacy, evidence-only grounding entries (retained for
                         backwards compatibility with existing callers).
        grounding_items: Generalized, domain-agnostic grounding items.  This is
                         the canonical surface providers should read.  Derived
                         from ``evidence_items`` when not supplied directly.
        max_tokens:      Maximum token budget for the response.
        temperature:     Sampling temperature for the model.  Defaults to
                         ``0.0`` — regulated intelligence favours the most
                         deterministic decoding available (Principle XII).  A
                         provider MUST clamp/translate this into whatever range
                         its backend expects; the interface value is engine-agnostic.
        system_prompt:   Optional caller-supplied system instruction.  When
                         ``None`` the provider applies its own governed default
                         (e.g. a "answer only from the supplied grounding and
                         cite each ref" guardrail).  Kept optional so callers
                         such as ``CopilotService`` need not author prompt text
                         to use inference — the provider owns a safe default.
        thinking_budget: Optional cap (in tokens) on a reasoning model's
                         internal "thinking" tokens, which share the same
                         response budget as ``max_tokens`` on providers that
                         support extended thinking (confirmed live for Gemini
                         2.5: thinking-token consumption is dynamic per call,
                         not fixed by ``temperature``, and can vary enough
                         between otherwise-identical calls to truncate the
                         visible answer even at a generous ``max_tokens``).
                         ``None`` leaves the provider's own default dynamic
                         budget in place. ``0`` disables extended thinking —
                         appropriate for deterministic, mechanical tasks (e.g.
                         Finding generation's "compare records, list
                         discrepancies") where the full visible answer
                         reliably fitting the budget matters more than any
                         quality gain from extended reasoning. A provider that
                         does not support this MUST ignore it.
    """

    application_id: str
    query: str
    prompt_version: str
    evidence_items: tuple[EvidenceEntry, ...] = ()
    grounding_items: tuple[GroundingItem, ...] = ()
    max_tokens: int = 1024
    temperature: float = 0.0
    system_prompt: str | None = None
    thinking_budget: int | None = None

    def __post_init__(self) -> None:
        if not self.application_id:
            raise ValueError("application_id cannot be empty")
        if not self.query:
            raise ValueError("query cannot be empty")
        if not self.prompt_version:
            raise ValueError("prompt_version cannot be empty")
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")
        if self.temperature < 0.0:
            raise ValueError("temperature cannot be negative")
        if self.thinking_budget is not None and self.thinking_budget < 0:
            raise ValueError("thinking_budget cannot be negative")
        # Backwards-compat bridge: normalise legacy evidence entries into the
        # generalized grounding surface so downstream providers only ever read
        # ``grounding_items``.  A caller that supplies ``grounding_items``
        # directly is never overridden.
        if self.evidence_items and not self.grounding_items:
            derived = tuple(
                GroundingItem(
                    kind=_EVIDENCE_KIND,
                    ref=entry.evidence_ref,
                    summary=f"{entry.field_name}: {entry.field_value}",
                    provenance=(
                        f"{entry.source_ref}#page={entry.page_number}" if entry.source_ref else None
                    ),
                    confidence=entry.confidence,
                )
                for entry in self.evidence_items
            )
            object.__setattr__(self, "grounding_items", derived)


@dataclasses.dataclass(frozen=True)
class InferenceResult:
    """
    Structured result from a single inference call.

    Both ``model_version`` and ``prompt_version`` are required to satisfy
    Engineering Constitution Principle XII (Deterministic Intelligence).
    Every AI-generated finding derived from this result MUST record both
    versions in its attribution fields.

    Attributes:
        content:             The natural-language response from the model.
        model_version:       The identifier of the AI model used (e.g. version
                             hash, tag, or release name).  MUST be non-empty.
        prompt_version:      The version of the prompt template applied (echoed
                             from ``InferenceContext.prompt_version``).
        evidence_citations:  Tuple of ``evidence_ref`` values cited in the
                             response.  Each value must match an
                             ``EvidenceEntry.evidence_ref`` from the context.
        inference_latency_ms: Wall-clock time for the inference call in milliseconds.
                             Used for operational monitoring.
    """

    content: str
    model_version: str
    prompt_version: str
    evidence_citations: tuple[str, ...]
    inference_latency_ms: float = 0.0

    def __post_init__(self) -> None:
        if not self.model_version:
            raise ValueError("model_version cannot be empty")
        if not self.prompt_version:
            raise ValueError("prompt_version cannot be empty")
        if self.inference_latency_ms < 0.0:
            raise ValueError("inference_latency_ms cannot be negative")


# ---------------------------------------------------------------------------
# Abstract InferenceProvider interface
# ---------------------------------------------------------------------------


class InferenceProvider(ABC):
    """
    Abstract interface for prompted AI inference.

    Executes a prompt against a scoped evidence context and returns a
    structured result.  The interface is engine-agnostic: concrete
    implementations may call on-premises models, managed cloud endpoints,
    or in-process libraries.

    Security requirement (Principle V): the provider MUST enforce that data
    passed to the model is scoped to the evidence items in the context.
    Evidence from one ``application_id`` MUST NOT appear in inference
    results for a different ``application_id``.

    Version contract: every ``InferenceResult`` MUST include non-empty
    ``model_version`` and ``prompt_version`` strings.  Providers that cannot
    determine their own model version MUST raise ``ProviderVersionMissingError``.
    """

    @abstractmethod
    def infer(self, context: InferenceContext) -> InferenceResult:
        """
        Execute prompted inference against the provided evidence context.

        Args:
            context: A scoped ``InferenceContext`` containing evidence items
                     and the query to answer.

        Returns:
            ``InferenceResult`` with model version, prompt version, and citations.

        Raises:
            ProviderError:               If inference fails.
            ProviderVersionMissingError: If the model version cannot be determined.
        """

    @abstractmethod
    def version(self) -> str:
        """
        Return the model version identifier for this inference provider.

        Used by ``ProviderRegistry`` to validate provider registration and
        to pre-populate ``InferenceResult.model_version`` before a call.
        """
