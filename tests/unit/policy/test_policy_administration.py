"""Unit tests for Policy Administration (spec 005-enterprise-platform §4):
PolicyPackApproval model + PolicyService maker-checker methods, and the
PolicyResult.evaluated_rule_keys / passed_rule_keys addition (§3)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from mil.kernel.errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from mil.kernel.providers.policy import PolicyEvaluationResult, TriggeredRule
from mil.kernel.security import AuthenticatedUser, Role
from mil.policy.models import PolicyPack, PolicyPackApproval, PolicyResult
from mil.policy.service import PolicyService


def _admin_caller(tenant_id: object) -> AuthenticatedUser:
    return AuthenticatedUser(user_id=uuid4(), tenant_id=tenant_id, roles=frozenset({Role.ADMIN}))


def _readonly_caller(tenant_id: object) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(), tenant_id=tenant_id, roles=frozenset({Role.AUDIT_TEAM})
    )


# ---------------------------------------------------------------------------
# PolicyPackApproval model
# ---------------------------------------------------------------------------


class TestPolicyPackApprovalModel:
    def test_create_is_pending(self) -> None:
        approval = PolicyPackApproval.create(policy_pack_id=uuid4(), requested_by_user_id=uuid4())
        assert approval.decision == "PENDING"
        assert approval.is_approved is False

    def test_approve_sets_decided_fields(self) -> None:
        approval = PolicyPackApproval.create(policy_pack_id=uuid4(), requested_by_user_id=uuid4())
        decider = uuid4()
        approval.approve(decider)
        assert approval.is_approved is True
        assert approval.decided_by_user_id == decider

    def test_self_approval_rejected(self) -> None:
        requester = uuid4()
        approval = PolicyPackApproval.create(policy_pack_id=uuid4(), requested_by_user_id=requester)
        with pytest.raises(ValidationError):
            approval.approve(requester)

    def test_approve_twice_raises_conflict(self) -> None:
        approval = PolicyPackApproval.create(policy_pack_id=uuid4(), requested_by_user_id=uuid4())
        approval.approve(uuid4())
        with pytest.raises(ConflictError):
            approval.approve(uuid4())

    def test_reject_requires_reason(self) -> None:
        approval = PolicyPackApproval.create(policy_pack_id=uuid4(), requested_by_user_id=uuid4())
        with pytest.raises(ValidationError):
            approval.reject(uuid4(), "   ")

    def test_reject_records_reason(self) -> None:
        approval = PolicyPackApproval.create(policy_pack_id=uuid4(), requested_by_user_id=uuid4())
        approval.reject(uuid4(), "Missing required disclosure language")
        assert approval.decision == "REJECTED"
        assert approval.reason == "Missing required disclosure language"


# ---------------------------------------------------------------------------
# PolicyResult.evaluated_rule_keys / passed_rule_keys
# ---------------------------------------------------------------------------


class TestPolicyResultPassedRuleKeys:
    def _make_result(self, *, evaluated_rule_keys: list[str] | None) -> PolicyResult:
        eval_result = PolicyEvaluationResult(
            outcome="FLAGGED",
            triggered_rules=(TriggeredRule(rule_key="LOW_CONFIDENCE", severity="MEDIUM"),),
            policy_version="v1",
            evaluated_at=datetime(2026, 7, 11, tzinfo=UTC),
        )
        return PolicyResult.create(
            finding_id=uuid4(),
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            policy_pack_id=uuid4(),
            result=eval_result,
            evaluated_rule_keys=evaluated_rule_keys,
        )

    def test_passed_rule_keys_none_when_not_recorded(self) -> None:
        result = self._make_result(evaluated_rule_keys=None)
        assert result.passed_rule_keys is None

    def test_passed_rule_keys_excludes_triggered(self) -> None:
        result = self._make_result(
            evaluated_rule_keys=["LOW_CONFIDENCE", "INCOME_MISMATCH", "MISSING_DOCUMENT"]
        )
        assert result.passed_rule_keys == ["INCOME_MISMATCH", "MISSING_DOCUMENT"]


# ---------------------------------------------------------------------------
# PolicyService maker-checker methods
# ---------------------------------------------------------------------------


class FakePolicyRepository:
    def __init__(self) -> None:
        self.packs: dict[object, PolicyPack] = {}
        self.approvals: dict[object, PolicyPackApproval] = {}

    def save_pack(self, pack: PolicyPack) -> None:
        self.packs[pack.id] = pack

    def get_pack_by_id(self, pack_id: object) -> PolicyPack | None:
        return self.packs.get(pack_id)

    def get_active_pack_for_tenant(self, tenant_id: object) -> PolicyPack | None:
        for pack in self.packs.values():
            if pack.tenant_id == tenant_id and pack.is_active:
                return pack
        return None

    def get_packs_for_tenant(self, tenant_id: object) -> list[PolicyPack]:
        return [p for p in self.packs.values() if p.tenant_id == tenant_id]

    def save_approval(self, approval: PolicyPackApproval) -> None:
        self.approvals[approval.id] = approval

    def get_pending_approval_for_pack(self, policy_pack_id: object) -> PolicyPackApproval | None:
        for a in self.approvals.values():
            if a.policy_pack_id == policy_pack_id and a.decision == "PENDING":
                return a
        return None

    def get_approved_approval_for_pack(self, policy_pack_id: object) -> PolicyPackApproval | None:
        for a in self.approvals.values():
            if a.policy_pack_id == policy_pack_id and a.decision == "APPROVED":
                return a
        return None

    def get_approvals_for_pack(self, policy_pack_id: object) -> list[PolicyPackApproval]:
        return [a for a in self.approvals.values() if a.policy_pack_id == policy_pack_id]


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


def _make_pack(repo: FakePolicyRepository, tenant_id: object) -> PolicyPack:
    pack = PolicyPack.create(
        tenant_id=tenant_id, version="1.0.0", name="Standard Pack", content_hash="a" * 8
    )
    repo.save_pack(pack)
    return pack


class TestMakerCheckerWorkflow:
    def test_submit_creates_pending_approval(self) -> None:
        service, repo, audit = _make_service()
        tenant_id = uuid4()
        caller = _admin_caller(tenant_id)
        pack = _make_pack(repo, tenant_id)

        approval = service.submit_for_approval(caller, pack)

        assert approval.decision == "PENDING"
        assert audit.records[-1]["event_type"] == "POLICY_PACK_SUBMITTED_FOR_APPROVAL"

    def test_submit_twice_raises_conflict(self) -> None:
        service, repo, _ = _make_service()
        tenant_id = uuid4()
        caller = _admin_caller(tenant_id)
        pack = _make_pack(repo, tenant_id)
        service.submit_for_approval(caller, pack)

        with pytest.raises(ConflictError):
            service.submit_for_approval(caller, pack)

    def test_activate_without_approval_raises_not_found(self) -> None:
        service, repo, _ = _make_service()
        tenant_id = uuid4()
        caller = _admin_caller(tenant_id)
        pack = _make_pack(repo, tenant_id)

        with pytest.raises(NotFoundError):
            service.activate_pack_if_approved(caller, pack)

    def test_full_cycle_submit_approve_activate(self) -> None:
        service, repo, audit = _make_service()
        tenant_id = uuid4()
        drafter = _admin_caller(tenant_id)
        approver = _admin_caller(tenant_id)
        pack = _make_pack(repo, tenant_id)

        approval = service.submit_for_approval(drafter, pack)
        service.approve_pack(approver, approval, tenant_id=tenant_id)
        activated = service.activate_pack_if_approved(approver, pack)

        assert activated.is_active is True
        assert audit.records[-1]["event_type"] == "POLICY_PACK_ACTIVATED"

    def test_reject_records_reason_and_blocks_activation(self) -> None:
        service, repo, audit = _make_service()
        tenant_id = uuid4()
        drafter = _admin_caller(tenant_id)
        approver = _admin_caller(tenant_id)
        pack = _make_pack(repo, tenant_id)

        approval = service.submit_for_approval(drafter, pack)
        service.reject_pack(approver, approval, tenant_id=tenant_id, reason="Needs revision")

        assert audit.records[-1]["event_type"] == "POLICY_PACK_REJECTED"
        with pytest.raises(NotFoundError):
            service.activate_pack_if_approved(approver, pack)

    def test_readonly_role_cannot_approve(self) -> None:
        service, repo, _ = _make_service()
        tenant_id = uuid4()
        drafter = _admin_caller(tenant_id)
        pack = _make_pack(repo, tenant_id)
        approval = service.submit_for_approval(drafter, pack)

        readonly = _readonly_caller(tenant_id)
        with pytest.raises(AuthorizationError):
            service.approve_pack(readonly, approval, tenant_id=tenant_id)
