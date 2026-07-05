"""Unit tests for mil.policy.repository — PolicyRepository."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from mil.kernel.providers.policy import PolicyEvaluationResult
from mil.policy.models import PolicyPack, PolicyResult, PolicyRule
from mil.policy.repository import PolicyRepository


def _pack() -> PolicyPack:
    return PolicyPack.create(tenant_id=uuid4(), version="1.0.0", name="Pack", content_hash="hash")


def _rule() -> PolicyRule:
    return PolicyRule.create(
        policy_pack_id=uuid4(),
        rule_key="LOW_CONFIDENCE_REVIEW",
        name="Low Confidence Review",
        description="desc",
        severity="MEDIUM",
    )


def _result() -> PolicyResult:
    return PolicyResult.create(
        finding_id=uuid4(),
        application_id=uuid4(),
        tenant_id=uuid4(),
        workflow_run_id=uuid4(),
        policy_pack_id=uuid4(),
        result=PolicyEvaluationResult(
            outcome="PASS",
            triggered_rules=(),
            policy_version="mock-policy-1.0.0",
            evaluated_at=datetime(2026, 7, 2, 12, 0, tzinfo=UTC),
        ),
    )


def _make_repo() -> tuple[PolicyRepository, MagicMock]:
    session = MagicMock()
    return PolicyRepository(session), session


class TestSavePack:
    def test_adds_and_flushes(self) -> None:
        repo, session = _make_repo()
        pack = _pack()
        repo.save_pack(pack)
        session.add.assert_called_once_with(pack)
        session.flush.assert_called_once()


class TestGetPackById:
    def test_returns_pack(self) -> None:
        repo, session = _make_repo()
        pack = _pack()
        session.get.return_value = pack
        assert repo.get_pack_by_id(pack.id) is pack

    def test_returns_none_when_missing(self) -> None:
        repo, session = _make_repo()
        session.get.return_value = None
        assert repo.get_pack_by_id(uuid4()) is None


class TestGetActivePackForTenant:
    def test_returns_active_pack(self) -> None:
        repo, session = _make_repo()
        pack = _pack()
        session.scalars.return_value.one_or_none.return_value = pack
        assert repo.get_active_pack_for_tenant(uuid4()) is pack

    def test_returns_none_when_no_active_pack(self) -> None:
        repo, session = _make_repo()
        session.scalars.return_value.one_or_none.return_value = None
        assert repo.get_active_pack_for_tenant(uuid4()) is None


class TestGetPacksForTenant:
    def test_returns_list(self) -> None:
        repo, session = _make_repo()
        p1, p2 = _pack(), _pack()
        session.scalars.return_value = iter([p1, p2])
        assert repo.get_packs_for_tenant(uuid4()) == [p1, p2]


class TestSaveRule:
    def test_adds_and_flushes(self) -> None:
        repo, session = _make_repo()
        rule = _rule()
        repo.save_rule(rule)
        session.add.assert_called_once_with(rule)
        session.flush.assert_called_once()


class TestGetRulesForPack:
    def test_returns_list(self) -> None:
        repo, session = _make_repo()
        r1, r2 = _rule(), _rule()
        session.scalars.return_value = iter([r1, r2])
        assert repo.get_rules_for_pack(uuid4()) == [r1, r2]


class TestSaveResult:
    def test_adds_and_flushes(self) -> None:
        repo, session = _make_repo()
        result = _result()
        repo.save_result(result)
        session.add.assert_called_once_with(result)
        session.flush.assert_called_once()

    def test_does_not_commit(self) -> None:
        repo, session = _make_repo()
        repo.save_result(_result())
        session.commit.assert_not_called()


class TestExistsForFindingAndVersion:
    def test_true_when_present(self) -> None:
        repo, session = _make_repo()
        session.scalars.return_value.first.return_value = uuid4()
        assert repo.exists_for_finding_and_version(uuid4(), "mock-policy-1.0.0") is True

    def test_false_when_absent(self) -> None:
        repo, session = _make_repo()
        session.scalars.return_value.first.return_value = None
        assert repo.exists_for_finding_and_version(uuid4(), "mock-policy-1.0.0") is False


class TestGetForFinding:
    def test_returns_list(self) -> None:
        repo, session = _make_repo()
        r1, r2 = _result(), _result()
        session.scalars.return_value = iter([r1, r2])
        assert repo.get_for_finding(uuid4()) == [r1, r2]
