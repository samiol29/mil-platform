"""
MockPolicyProvider — development Policy provider.

Deterministically evaluates a Finding against its available rule catalogue:
if a rule keyed ``LOW_CONFIDENCE_REVIEW`` is present and the Finding's
confidence score is below the threshold, that rule is triggered and the
outcome is ``FLAGGED``. Otherwise the outcome is ``PASS`` and no rules are
triggered.

Intended for local development, unit tests, and conformance test verification.
MUST NOT be registered in staging or production containers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mil.kernel.providers.policy import (
    PolicyEvaluationResult,
    PolicyProvider,
    TriggeredRule,
    make_policy_evaluation_result,
)

if TYPE_CHECKING:
    from mil.kernel.providers.policy import PolicyEvaluationContext

_VERSION = "mock-policy-1.0.0"

_LOW_CONFIDENCE_RULE_KEY = "LOW_CONFIDENCE_REVIEW"
_LOW_CONFIDENCE_THRESHOLD = 0.70

_OUTCOME_PASS = "PASS"
_OUTCOME_FLAGGED = "FLAGGED"


class MockPolicyProvider(PolicyProvider):
    """
    Deterministic Policy provider for development and testing.

    Triggers ``LOW_CONFIDENCE_REVIEW`` — if present in
    ``context.available_rules`` — whenever the Finding's confidence score is
    below 0.70. Any other rule in the catalogue is never triggered by this
    mock (it exists only to exercise multi-rule catalogues in tests). No
    other verification logic is implemented; a real provider supplies it.
    """

    def evaluate(self, context: PolicyEvaluationContext) -> PolicyEvaluationResult:
        triggered: list[TriggeredRule] = []

        if context.confidence_score < _LOW_CONFIDENCE_THRESHOLD:
            rule = next(
                (r for r in context.available_rules if r.rule_key == _LOW_CONFIDENCE_RULE_KEY),
                None,
            )
            if rule is not None:
                triggered.append(
                    TriggeredRule(
                        rule_key=rule.rule_key,
                        severity=rule.severity,
                        reason=(
                            f"Confidence score {context.confidence_score:.2f} is below the "
                            f"{_LOW_CONFIDENCE_THRESHOLD:.2f} threshold"
                        ),
                    )
                )

        outcome = _OUTCOME_FLAGGED if triggered else _OUTCOME_PASS

        return make_policy_evaluation_result(
            outcome=outcome,
            triggered_rules=tuple(triggered),
            policy_version=_VERSION,
        )

    def version(self) -> str:
        return _VERSION
