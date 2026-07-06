"""Unit tests for mil.policy.service — PolicyService."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from mil.kernel.errors import ConflictError
from mil.kernel.providers.policy import PolicyEvaluationResult, TriggeredRule
from mil.policy.models import PolicyPack, PolicyResult
from mil.policy.service import PolicyService

if TYPE_CHECKING:
    from mil.policy.models import PolicyRule


class FakePolicyRepository:
    def __init__(self) -> None:
        self.saved_packs: list[PolicyPack] = []
        self.saved_rules: list[PolicyRule] = []
        self.saved_results: list[PolicyResult] = []
        self._active_pack: PolicyPack | None = None
        self.force_collision = False
        self.collision_existing: PolicyResult | None = None

    def save_pack(self, pack: PolicyPack) -> None:
        self.saved_packs.append(pack)

    def save_rule(self, rule: PolicyRule) -> None:
        self.saved_rules.append(rule)

    def save_result(self, result: PolicyResult) -> None:
        self.saved_results.append(result)

    def save_result_if_not_exists(self, result: PolicyResult) -> bool:
        if self.force_collision:
            return False
        self.save_result(result)
        return True

    def get_by_finding_and_version(
        self, finding_id: object, policy_version: str
    ) -> PolicyResult | None:
        return self.collision_existing

    def get_active_pack_for_tenant(self, tenant_id: object) -> PolicyPack | None:
        return self._active_pack

    def seed_active_pack(self, pack: PolicyPack) -> None:
        self._active_pack = pack


class FakeAuditWriter:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record(self, **kwargs: object) -> object:
        self.records.append(kwargs)
        return object()


def _make_service() -> tuple[PolicyService, FakePolicyRepository, FakeAuditWriter]:
    repo = FakePolicyRepository()
    audit = FakeAuditWriter()
    return PolicyService(repo, audit), repo, audit  # type: ignore[arg-type]


def _evaluation_result(**overrides: object) -> PolicyEvaluationResult:
    kwargs: dict[str, object] = {
        "outcome": "FLAGGED",
        "triggered_rules": (TriggeredRule(rule_key="LOW_CONFIDENCE_REVIEW", severity="MEDIUM"),),
        "policy_version": "mock-policy-1.0.0",
        "evaluated_at": datetime(2026, 7, 2, 12, 0, tzinfo=UTC),
    }
    kwargs.update(overrides)
    return PolicyEvaluationResult(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Policy Pack lifecycle
# ---------------------------------------------------------------------------


class TestCreatePack:
    def test_creates_inactive_pack(self) -> None:
        service, repo, _ = _make_service()
        pack = service.create_pack(
            tenant_id=uuid4(), version="1.0.0", name="Pack", content_hash="hash"
        )
        assert pack.is_active is False
        assert pack in repo.saved_packs

    def test_emits_policy_pack_created_audit_event(self) -> None:
        service, _, audit = _make_service()
        service.create_pack(tenant_id=uuid4(), version="1.0.0", name="Pack", content_hash="hash")
        assert audit.records[0]["event_type"] == "POLICY_PACK_CREATED"


class TestActivatePack:
    def test_activates_pack(self) -> None:
        service, _, _ = _make_service()
        pack = PolicyPack.create(
            tenant_id=uuid4(), version="1.0.0", name="Pack", content_hash="hash"
        )
        service.activate_pack(pack)
        assert pack.is_active is True

    def test_raises_when_another_pack_already_active(self) -> None:
        service, repo, _ = _make_service()
        tenant_id = uuid4()
        existing = PolicyPack.create(
            tenant_id=tenant_id, version="1.0.0", name="Existing", content_hash="hash"
        )
        existing.activate()
        repo.seed_active_pack(existing)

        new_pack = PolicyPack.create(
            tenant_id=tenant_id, version="2.0.0", name="New", content_hash="hash2"
        )
        with pytest.raises(ConflictError):
            service.activate_pack(new_pack)

    def test_emits_policy_pack_activated_audit_event(self) -> None:
        service, _, audit = _make_service()
        pack = PolicyPack.create(
            tenant_id=uuid4(), version="1.0.0", name="Pack", content_hash="hash"
        )
        service.activate_pack(pack)
        assert audit.records[0]["event_type"] == "POLICY_PACK_ACTIVATED"


class TestDeactivatePack:
    def test_deactivates_pack(self) -> None:
        service, _, _ = _make_service()
        pack = PolicyPack.create(
            tenant_id=uuid4(), version="1.0.0", name="Pack", content_hash="hash"
        )
        pack.activate()
        service.deactivate_pack(pack)
        assert pack.is_active is False

    def test_emits_policy_pack_deactivated_audit_event(self) -> None:
        service, _, audit = _make_service()
        pack = PolicyPack.create(
            tenant_id=uuid4(), version="1.0.0", name="Pack", content_hash="hash"
        )
        pack.activate()
        service.deactivate_pack(pack)
        assert audit.records[0]["event_type"] == "POLICY_PACK_DEACTIVATED"


class TestAddRule:
    def test_creates_rule(self) -> None:
        service, repo, _ = _make_service()
        rule = service.add_rule(
            policy_pack_id=uuid4(),
            tenant_id=uuid4(),
            rule_key="LOW_CONFIDENCE_REVIEW",
            name="Low Confidence Review",
            description="desc",
            severity="MEDIUM",
        )
        assert rule in repo.saved_rules

    def test_emits_policy_rule_added_audit_event(self) -> None:
        service, _, audit = _make_service()
        service.add_rule(
            policy_pack_id=uuid4(),
            tenant_id=uuid4(),
            rule_key="LOW_CONFIDENCE_REVIEW",
            name="Low Confidence Review",
            description="desc",
            severity="MEDIUM",
        )
        assert audit.records[0]["event_type"] == "POLICY_RULE_ADDED"


# ---------------------------------------------------------------------------
# Policy result persistence (the Policy worker's use case)
# ---------------------------------------------------------------------------


class TestRecordPolicyResult:
    def test_creates_one_result(self) -> None:
        service, repo, _ = _make_service()
        service.record_policy_result(
            finding_id=uuid4(),
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            policy_pack_id=uuid4(),
            result=_evaluation_result(),
        )
        assert len(repo.saved_results) == 1

    def test_records_outcome_and_version(self) -> None:
        service, repo, _ = _make_service()
        service.record_policy_result(
            finding_id=uuid4(),
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            policy_pack_id=uuid4(),
            result=_evaluation_result(outcome="REJECTED", policy_version="v9"),
        )
        assert repo.saved_results[0].outcome == "REJECTED"
        assert repo.saved_results[0].policy_version == "v9"

    def test_emits_policy_evaluated_audit_event(self) -> None:
        service, _, audit = _make_service()
        service.record_policy_result(
            finding_id=uuid4(),
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            policy_pack_id=uuid4(),
            result=_evaluation_result(),
        )
        assert audit.records[0]["event_type"] == "POLICY_EVALUATED"
        assert audit.records[0]["entity_type"] == "POLICY_RESULT"

    def test_audit_event_carries_tenant_and_application(self) -> None:
        service, _, audit = _make_service()
        app_id, tenant_id = uuid4(), uuid4()
        service.record_policy_result(
            finding_id=uuid4(),
            application_id=app_id,
            tenant_id=tenant_id,
            workflow_run_id=uuid4(),
            policy_pack_id=uuid4(),
            result=_evaluation_result(),
        )
        assert audit.records[0]["tenant_id"] == tenant_id
        assert audit.records[0]["application_id"] == app_id

    def test_links_result_to_finding_and_run(self) -> None:
        service, repo, _ = _make_service()
        finding_id, run_id = uuid4(), uuid4()
        service.record_policy_result(
            finding_id=finding_id,
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=run_id,
            policy_pack_id=uuid4(),
            result=_evaluation_result(),
        )
        assert repo.saved_results[0].finding_id == finding_id
        assert repo.saved_results[0].workflow_run_id == run_id

    def test_returns_created_true_on_first_call(self) -> None:
        service, _, _ = _make_service()
        _, created = service.record_policy_result(
            finding_id=uuid4(),
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            policy_pack_id=uuid4(),
            result=_evaluation_result(),
        )
        assert created is True

    def test_replay_collision_returns_existing_result_without_duplicate_audit(self) -> None:
        """ADR-008 §5: a uniqueness collision on create is a no-op, not an error."""
        service, repo, audit = _make_service()
        finding_id = uuid4()
        existing = PolicyResult.create(
            finding_id=finding_id,
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            policy_pack_id=uuid4(),
            result=_evaluation_result(),
        )
        repo.force_collision = True
        repo.collision_existing = existing

        result, created = service.record_policy_result(
            finding_id=finding_id,
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            policy_pack_id=uuid4(),
            result=_evaluation_result(),
        )

        assert created is False
        assert result is existing
        assert repo.saved_results == []
        assert audit.records == []
