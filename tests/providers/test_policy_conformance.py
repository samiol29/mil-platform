"""
PolicyProvider conformance tests.

Verifies that any concrete ``PolicyProvider`` satisfies the interface
contract defined in ``mil.kernel.providers.policy``, including mandatory
presence of policy version attribution on every result.

Engineering Constitution Principle XII (Deterministic Intelligence): every
Policy evaluation must be attributable to a specific policy engine version.
"""

from __future__ import annotations

import pytest

from mil.kernel.providers.policy import (
    PolicyEvaluationContext,
    PolicyEvaluationResult,
    PolicyProvider,
    PolicyRuleDefinition,
)

# ---------------------------------------------------------------------------
# Shared context builder
# ---------------------------------------------------------------------------


def make_context(
    confidence_score: float = 0.90,
    available_rules: tuple[PolicyRuleDefinition, ...] | None = None,
) -> PolicyEvaluationContext:
    if available_rules is None:
        available_rules = (
            PolicyRuleDefinition(
                rule_key="LOW_CONFIDENCE_REVIEW",
                name="Low Confidence Review",
                severity="MEDIUM",
                description="Flags findings below the confidence threshold.",
            ),
        )
    return PolicyEvaluationContext(
        application_id="app-001",
        finding_ref="finding-001",
        finding_type="AI_GENERATED_ASSESSMENT",
        confidence_score=confidence_score,
        evidence_summary="gross_monthly_income=5000.00",
        available_rules=available_rules,
    )


class TestPolicyProviderInterfaceContract:
    """Verify the abstract interface structure."""

    def test_policy_provider_is_abstract(self) -> None:
        assert PolicyProvider.__abstractmethods__ != set()

    def test_evaluate_is_abstract(self) -> None:
        assert "evaluate" in PolicyProvider.__abstractmethods__

    def test_version_is_abstract(self) -> None:
        assert "version" in PolicyProvider.__abstractmethods__

    def test_concrete_provider_is_subclass(self, policy_provider: PolicyProvider) -> None:
        assert isinstance(policy_provider, PolicyProvider)


class TestPolicyProviderVersion:
    """Version contract: providers MUST return a non-empty policy version string."""

    def test_version_returns_string(self, policy_provider: PolicyProvider) -> None:
        assert isinstance(policy_provider.version(), str)

    def test_version_is_non_empty(self, policy_provider: PolicyProvider) -> None:
        assert policy_provider.version() != ""


class TestEvaluateResultStructure:
    """PolicyEvaluationResult must carry required attribution fields."""

    @pytest.fixture
    def result(self, policy_provider: PolicyProvider) -> PolicyEvaluationResult:
        return policy_provider.evaluate(make_context())

    def test_returns_policy_evaluation_result(self, result: PolicyEvaluationResult) -> None:
        assert isinstance(result, PolicyEvaluationResult)

    def test_outcome_is_non_empty(self, result: PolicyEvaluationResult) -> None:
        assert isinstance(result.outcome, str)
        assert result.outcome != ""

    # Principle XII: policy version required
    def test_policy_version_is_non_empty(self, result: PolicyEvaluationResult) -> None:
        assert isinstance(result.policy_version, str)
        assert result.policy_version != ""

    def test_policy_version_matches_provider_version(
        self, policy_provider: PolicyProvider, result: PolicyEvaluationResult
    ) -> None:
        assert result.policy_version == policy_provider.version()

    def test_triggered_rules_is_tuple(self, result: PolicyEvaluationResult) -> None:
        assert isinstance(result.triggered_rules, tuple)

    def test_evaluated_at_is_timezone_aware(self, result: PolicyEvaluationResult) -> None:
        assert result.evaluated_at.tzinfo is not None


class TestPolicyRuleScoping:
    """Triggered rules must reference only rule_keys in the context's catalogue."""

    def test_triggered_rules_are_subset_of_available_rules(
        self, policy_provider: PolicyProvider
    ) -> None:
        context = make_context(confidence_score=0.1)
        available_keys = {r.rule_key for r in context.available_rules}
        result = policy_provider.evaluate(context)

        for triggered in result.triggered_rules:
            assert triggered.rule_key in available_keys, (
                f"Triggered rule {triggered.rule_key!r} not in available rules "
                f"{available_keys!r}. Provider MUST NOT trigger a rule outside "
                "the supplied catalogue."
            )

    def test_empty_rule_catalogue_triggers_nothing(self, policy_provider: PolicyProvider) -> None:
        context = make_context(confidence_score=0.1, available_rules=())
        result = policy_provider.evaluate(context)
        assert result.triggered_rules == ()


class TestPolicyEvaluationContextValidation:
    """PolicyEvaluationContext rejects invalid inputs at construction time."""

    def test_empty_application_id_raises(self) -> None:
        with pytest.raises(ValueError, match="application_id"):
            PolicyEvaluationContext(
                application_id="",
                finding_ref="f-1",
                finding_type="TYPE",
                confidence_score=0.5,
                evidence_summary="",
                available_rules=(),
            )

    def test_empty_finding_ref_raises(self) -> None:
        with pytest.raises(ValueError, match="finding_ref"):
            PolicyEvaluationContext(
                application_id="app-1",
                finding_ref="",
                finding_type="TYPE",
                confidence_score=0.5,
                evidence_summary="",
                available_rules=(),
            )

    def test_out_of_range_confidence_raises(self) -> None:
        with pytest.raises(ValueError, match="confidence_score"):
            PolicyEvaluationContext(
                application_id="app-1",
                finding_ref="f-1",
                finding_type="TYPE",
                confidence_score=1.5,
                evidence_summary="",
                available_rules=(),
            )


class TestPolicyEvaluationResultValidation:
    """PolicyEvaluationResult rejects invalid inputs at construction time."""

    def test_empty_outcome_raises(self) -> None:
        from datetime import UTC, datetime

        with pytest.raises(ValueError, match="outcome"):
            PolicyEvaluationResult(
                outcome="",
                triggered_rules=(),
                policy_version="v1",
                evaluated_at=datetime.now(UTC),
            )

    def test_empty_policy_version_raises(self) -> None:
        from datetime import UTC, datetime

        with pytest.raises(ValueError, match="policy_version"):
            PolicyEvaluationResult(
                outcome="PASS",
                triggered_rules=(),
                policy_version="",
                evaluated_at=datetime.now(UTC),
            )

    def test_naive_evaluated_at_raises(self) -> None:
        from datetime import datetime

        with pytest.raises(ValueError, match="timezone-aware"):
            PolicyEvaluationResult(
                outcome="PASS",
                triggered_rules=(),
                policy_version="v1",
                evaluated_at=datetime(2026, 7, 1, 12, 0),
            )
