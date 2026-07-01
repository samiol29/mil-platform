"""
PolicyProvider interface for the MIL Platform.

Evaluates a single Finding against the rule catalogue of the active Policy
Pack and returns a structured, versioned result. All verification logic lives
inside the concrete provider implementation — this module, and the bounded
context code that constructs its inputs, never hardcodes a rule (Engineering
Constitution Principle IX; tasks.md T064: "never hardcodes verification logic").

This module defines only the abstract interface and its data types.
Concrete implementations live in ``src/providers/policy/`` and are
registered via ``ProviderRegistry.register_policy()``.

Dependency rule: this module imports from the Python standard library only.
No bounded context code should be imported here.
"""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from datetime import UTC, datetime

# ---------------------------------------------------------------------------
# Policy evaluation data types
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class PolicyRuleDefinition:
    """
    A single rule available for evaluation, scoped from the active Policy Pack.

    Domain-agnostic: carries only what a provider needs to decide whether the
    rule is triggered, not the ``PolicyRule`` ORM entity itself.
    """

    rule_key: str
    name: str
    severity: str
    description: str = ""

    def __post_init__(self) -> None:
        if not self.rule_key:
            raise ValueError("rule_key cannot be empty")
        if not self.severity:
            raise ValueError("severity cannot be empty")


@dataclasses.dataclass(frozen=True)
class PolicyEvaluationContext:
    """
    Scoped context for a single Policy evaluation call.

    Constructed by the Policy worker from a persisted ``Finding`` and the
    rule catalogue of the tenant's active Policy Pack. Contains only the
    attributes needed to decide which rules are triggered — no surplus
    personal data (Principle V).

    Attributes:
        application_id:   The MIL application ID (for scope enforcement).
        finding_ref:       Identifier of the Finding being evaluated.
        finding_type:      The Finding's machine-readable classifier.
        confidence_score:  The Finding's raw confidence score, [0.0, 1.0].
        evidence_summary:  Plain-text summary of the Finding's supporting evidence.
        available_rules:   The rule catalogue of the active Policy Pack.
    """

    application_id: str
    finding_ref: str
    finding_type: str
    confidence_score: float
    evidence_summary: str
    available_rules: tuple[PolicyRuleDefinition, ...]

    def __post_init__(self) -> None:
        if not self.application_id:
            raise ValueError("application_id cannot be empty")
        if not self.finding_ref:
            raise ValueError("finding_ref cannot be empty")
        if not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError(f"confidence_score must be in [0.0, 1.0], got {self.confidence_score}")


@dataclasses.dataclass(frozen=True)
class TriggeredRule:
    """One rule from ``available_rules`` that the provider determined was triggered."""

    rule_key: str
    severity: str
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.rule_key:
            raise ValueError("rule_key cannot be empty")


@dataclasses.dataclass(frozen=True)
class PolicyEvaluationResult:
    """
    Structured result from a single Policy evaluation call.

    ``policy_version`` is required to satisfy Engineering Constitution
    Principle XII (Deterministic Intelligence). Every ``PolicyResult`` derived
    from this result MUST record it.

    Attributes:
        outcome:          Summary verdict, e.g. ``"PASS"``, ``"FLAGGED"``,
                          ``"REJECTED"``. MUST be non-empty.
        triggered_rules:  Tuple of ``TriggeredRule`` — empty when no rule in
                          ``available_rules`` was triggered.
        policy_version:   The identifier of the Policy provider/engine used.
                          MUST be non-empty.
        evaluated_at:     Timestamp of the evaluation. Timezone-aware.
    """

    outcome: str
    triggered_rules: tuple[TriggeredRule, ...]
    policy_version: str
    evaluated_at: datetime

    def __post_init__(self) -> None:
        if not self.outcome:
            raise ValueError("outcome cannot be empty")
        if not self.policy_version:
            raise ValueError("policy_version cannot be empty")
        if self.evaluated_at.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware")


# ---------------------------------------------------------------------------
# Abstract PolicyProvider interface
# ---------------------------------------------------------------------------


class PolicyProvider(ABC):
    """
    Abstract interface for Policy evaluation.

    Takes a scoped ``PolicyEvaluationContext`` describing one Finding and the
    rule catalogue of the active Policy Pack, and returns a structured,
    versioned ``PolicyEvaluationResult``.

    Version contract: every ``PolicyEvaluationResult`` MUST include a
    non-empty ``policy_version`` string. Providers that cannot determine
    their own version MUST raise ``ProviderVersionMissingError``.
    """

    @abstractmethod
    def evaluate(self, context: PolicyEvaluationContext) -> PolicyEvaluationResult:
        """
        Evaluate a Finding against the available Policy rules.

        Args:
            context: A scoped ``PolicyEvaluationContext``.

        Returns:
            ``PolicyEvaluationResult`` with the outcome, any triggered rules,
            and version attribution.

        Raises:
            ProviderError: If evaluation fails.
            ProviderVersionMissingError: If the policy version cannot be determined.
        """

    @abstractmethod
    def version(self) -> str:
        """
        Return the version identifier for this Policy provider implementation.

        This is the same string included in every
        ``PolicyEvaluationResult.policy_version``. Used by ``ProviderRegistry``
        to validate provider registration and by the Policy worker to validate
        against the workflow run's pinned policy version (ADR-009).
        """


# ---------------------------------------------------------------------------
# Helper to build a PolicyEvaluationResult with current UTC timestamp
# ---------------------------------------------------------------------------


def make_policy_evaluation_result(
    *,
    outcome: str,
    triggered_rules: tuple[TriggeredRule, ...],
    policy_version: str,
    evaluated_at: datetime | None = None,
) -> PolicyEvaluationResult:
    """
    Construct a ``PolicyEvaluationResult`` with the current UTC time by default.

    Pass an explicit ``evaluated_at`` in tests or when replaying historical
    evaluations.
    """
    ts = evaluated_at if evaluated_at is not None else datetime.now(UTC)
    return PolicyEvaluationResult(
        outcome=outcome,
        triggered_rules=triggered_rules,
        policy_version=policy_version,
        evaluated_at=ts,
    )
