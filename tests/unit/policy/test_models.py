"""Unit tests for mil.policy.models — PolicyPack, PolicyRule, PolicyResult."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from mil.kernel.errors import ConflictError, PolicyEvaluationError, ValidationError
from mil.kernel.providers.policy import PolicyEvaluationResult, TriggeredRule
from mil.policy.models import PolicyPack, PolicyResult, PolicyRule

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pack(**overrides: object) -> PolicyPack:
    kwargs: dict[str, object] = {
        "tenant_id": uuid4(),
        "version": "1.0.0",
        "name": "Standard Underwriting Pack",
        "content_hash": "deadbeef" * 8,
    }
    kwargs.update(overrides)
    return PolicyPack.create(**kwargs)  # type: ignore[arg-type]


def _make_rule(**overrides: object) -> PolicyRule:
    kwargs: dict[str, object] = {
        "policy_pack_id": uuid4(),
        "rule_key": "LOW_CONFIDENCE_REVIEW",
        "name": "Low Confidence Review",
        "description": "Flags findings below the confidence threshold.",
        "severity": "MEDIUM",
    }
    kwargs.update(overrides)
    return PolicyRule.create(**kwargs)  # type: ignore[arg-type]


def _evaluation_result(**overrides: object) -> PolicyEvaluationResult:
    kwargs: dict[str, object] = {
        "outcome": "FLAGGED",
        "triggered_rules": (
            TriggeredRule(rule_key="LOW_CONFIDENCE_REVIEW", severity="MEDIUM", reason="low score"),
        ),
        "policy_version": "mock-policy-1.0.0",
        "evaluated_at": datetime(2026, 7, 2, 12, 0, tzinfo=UTC),
    }
    kwargs.update(overrides)
    return PolicyEvaluationResult(**kwargs)  # type: ignore[arg-type]


def _make_result(**overrides: object) -> PolicyResult:
    kwargs: dict[str, object] = {
        "finding_id": uuid4(),
        "application_id": uuid4(),
        "tenant_id": uuid4(),
        "workflow_run_id": uuid4(),
        "policy_pack_id": uuid4(),
        "result": _evaluation_result(),
    }
    kwargs.update(overrides)
    return PolicyResult.create(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# PolicyPack
# ---------------------------------------------------------------------------


class TestPolicyPackCreate:
    def test_records_version_and_name(self) -> None:
        pack = _make_pack(version="2.1.0", name="Custom Pack")
        assert pack.version == "2.1.0"
        assert pack.name == "Custom Pack"

    def test_starts_inactive(self) -> None:
        pack = _make_pack()
        assert pack.activated_at is None
        assert pack.deactivated_at is None
        assert pack.is_active is False

    def test_records_jurisdiction(self) -> None:
        pack = _make_pack(jurisdiction="US-CA")
        assert pack.jurisdiction == "US-CA"

    def test_jurisdiction_defaults_to_none(self) -> None:
        assert _make_pack().jurisdiction is None

    def test_records_content_hash(self) -> None:
        pack = _make_pack(content_hash="abc123")
        assert pack.content_hash == "abc123"

    def test_records_created_by(self) -> None:
        user_id = uuid4()
        pack = _make_pack(created_by=user_id)
        assert pack.created_by == user_id

    def test_empty_version_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make_pack(version="")

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make_pack(name="")

    def test_empty_content_hash_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make_pack(content_hash="")


class TestPolicyPackLifecycle:
    def test_activate_sets_activated_at(self) -> None:
        pack = _make_pack()
        pack.activate()
        assert pack.activated_at is not None
        assert pack.is_active is True

    def test_activate_twice_raises(self) -> None:
        pack = _make_pack()
        pack.activate()
        with pytest.raises(ConflictError):
            pack.activate()

    def test_deactivate_sets_deactivated_at(self) -> None:
        pack = _make_pack()
        pack.activate()
        pack.deactivate()
        assert pack.deactivated_at is not None
        assert pack.is_active is False

    def test_deactivate_without_activate_raises(self) -> None:
        pack = _make_pack()
        with pytest.raises(ConflictError):
            pack.deactivate()

    def test_deactivate_twice_raises(self) -> None:
        pack = _make_pack()
        pack.activate()
        pack.deactivate()
        with pytest.raises(ConflictError):
            pack.deactivate()

    def test_reactivate_after_deactivate_raises(self) -> None:
        pack = _make_pack()
        pack.activate()
        pack.deactivate()
        with pytest.raises(ConflictError):
            pack.activate()


class TestPolicyPackOrmMetadata:
    def test_table_in_policy_schema(self) -> None:
        assert PolicyPack.__table__.schema == "policy"


# ---------------------------------------------------------------------------
# PolicyRule
# ---------------------------------------------------------------------------


class TestPolicyRuleCreate:
    def test_records_rule_key(self) -> None:
        rule = _make_rule(rule_key="HIGH_RISK_JURISDICTION")
        assert rule.rule_key == "HIGH_RISK_JURISDICTION"

    def test_records_severity(self) -> None:
        rule = _make_rule(severity="CRITICAL")
        assert rule.severity == "CRITICAL"

    def test_links_to_pack(self) -> None:
        pack_id = uuid4()
        rule = _make_rule(policy_pack_id=pack_id)
        assert rule.policy_pack_id == pack_id

    def test_empty_rule_key_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make_rule(rule_key="")

    def test_empty_severity_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make_rule(severity="")


class TestPolicyRuleOrmMetadata:
    def test_table_in_policy_schema(self) -> None:
        assert PolicyRule.__table__.schema == "policy"

    def test_unique_constraint_on_pack_and_rule_key(self) -> None:
        names = {c.name for c in PolicyRule.__table__.constraints}
        assert "uq_policy_rules_pack_rule_key" in names


# ---------------------------------------------------------------------------
# PolicyResult
# ---------------------------------------------------------------------------


class TestPolicyResultCreate:
    def test_records_outcome(self) -> None:
        result = _make_result(result=_evaluation_result(outcome="REJECTED"))
        assert result.outcome == "REJECTED"

    def test_records_policy_version(self) -> None:
        result = _make_result(result=_evaluation_result(policy_version="custom-v2"))
        assert result.policy_version == "custom-v2"

    def test_records_triggered_rule_keys(self) -> None:
        eval_result = _evaluation_result(
            triggered_rules=(
                TriggeredRule(rule_key="RULE_A", severity="LOW"),
                TriggeredRule(rule_key="RULE_B", severity="HIGH"),
            )
        )
        result = _make_result(result=eval_result)
        assert result.triggered_rule_keys == ["RULE_A", "RULE_B"]

    def test_no_triggered_rules_means_empty_list(self) -> None:
        eval_result = _evaluation_result(outcome="PASS", triggered_rules=())
        result = _make_result(result=eval_result)
        assert result.triggered_rule_keys == []

    def test_is_flagged_true_when_rules_triggered(self) -> None:
        result = _make_result()
        assert result.is_flagged is True

    def test_is_flagged_false_when_no_rules_triggered(self) -> None:
        result = _make_result(result=_evaluation_result(outcome="PASS", triggered_rules=()))
        assert result.is_flagged is False

    def test_records_evaluated_at(self) -> None:
        ts = datetime(2026, 6, 1, 9, 30, tzinfo=UTC)
        result = _make_result(result=_evaluation_result(evaluated_at=ts))
        assert result.evaluated_at == ts

    def test_sets_created_at(self) -> None:
        assert _make_result().created_at is not None

    def test_links_finding_application_run_and_pack(self) -> None:
        finding_id, app_id, run_id, pack_id = uuid4(), uuid4(), uuid4(), uuid4()
        result = _make_result(
            finding_id=finding_id,
            application_id=app_id,
            workflow_run_id=run_id,
            policy_pack_id=pack_id,
        )
        assert result.finding_id == finding_id
        assert result.application_id == app_id
        assert result.workflow_run_id == run_id
        assert result.policy_pack_id == pack_id


class TestPolicyResultAttributionEnforcement:
    def test_missing_outcome_raises_policy_evaluation_error(self) -> None:
        class _IncompleteResult:
            outcome = ""
            policy_version = "v1"
            triggered_rules: tuple[object, ...] = ()
            evaluated_at = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

        with pytest.raises(PolicyEvaluationError):
            PolicyResult.create(
                finding_id=uuid4(),
                application_id=uuid4(),
                tenant_id=uuid4(),
                workflow_run_id=uuid4(),
                policy_pack_id=uuid4(),
                result=_IncompleteResult(),  # type: ignore[arg-type]
            )

    def test_missing_policy_version_raises_policy_evaluation_error(self) -> None:
        class _IncompleteResult:
            outcome = "PASS"
            policy_version = ""
            triggered_rules: tuple[object, ...] = ()
            evaluated_at = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

        with pytest.raises(PolicyEvaluationError):
            PolicyResult.create(
                finding_id=uuid4(),
                application_id=uuid4(),
                tenant_id=uuid4(),
                workflow_run_id=uuid4(),
                policy_pack_id=uuid4(),
                result=_IncompleteResult(),  # type: ignore[arg-type]
            )


class TestPolicyResultOrmMetadata:
    def test_table_in_policy_schema(self) -> None:
        assert PolicyResult.__table__.schema == "policy"

    def test_unique_constraint_on_finding_and_policy_version(self) -> None:
        names = {c.name for c in PolicyResult.__table__.constraints}
        assert "uq_policy_results_finding_version" in names
