"""Unit tests for mil.orchestrator.repository — WorkflowRepository."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from mil.orchestrator.models import PinnedVersions, WorkflowRun
from mil.orchestrator.repository import WorkflowRepository


def _pinned() -> PinnedVersions:
    return PinnedVersions(policy="1.0.0", extraction="e1", inference="m1", prompt="p1")


def _make_run() -> WorkflowRun:
    return WorkflowRun.create(
        tenant_id=uuid4(),
        application_id=uuid4(),
        workflow_type="DOCUMENT_INGESTION",
        idempotency_key=f"DOCUMENT_INGESTION:{uuid4()}",
        correlation_id="corr-1",
        pinned_versions=_pinned(),
    )


def _make_repo() -> tuple[WorkflowRepository, MagicMock]:
    session = MagicMock()
    return WorkflowRepository(session), session


class TestSave:
    def test_save_adds_run_to_session(self) -> None:
        repo, session = _make_repo()
        run = _make_run()
        repo.save(run)
        session.add.assert_called_once_with(run)

    def test_save_flushes(self) -> None:
        repo, session = _make_repo()
        repo.save(_make_run())
        session.flush.assert_called_once()

    def test_save_does_not_commit(self) -> None:
        repo, session = _make_repo()
        repo.save(_make_run())
        session.commit.assert_not_called()


class TestGetById:
    def test_get_by_id_uses_session_get(self) -> None:
        repo, session = _make_repo()
        run_id = uuid4()
        repo.get_by_id(run_id)
        session.get.assert_called_once_with(WorkflowRun, run_id)

    def test_get_by_id_returns_none_when_missing(self) -> None:
        repo, session = _make_repo()
        session.get.return_value = None
        assert repo.get_by_id(uuid4()) is None


class TestGetByIdempotencyKey:
    def test_returns_existing_run(self) -> None:
        repo, session = _make_repo()
        run = _make_run()
        session.scalars.return_value.one_or_none.return_value = run
        result = repo.get_by_idempotency_key(run.idempotency_key)
        assert result is run

    def test_returns_none_when_missing(self) -> None:
        repo, session = _make_repo()
        session.scalars.return_value.one_or_none.return_value = None
        assert repo.get_by_idempotency_key("missing-key") is None


class TestGetForApplication:
    def test_returns_list(self) -> None:
        repo, session = _make_repo()
        r1, r2 = _make_run(), _make_run()
        session.scalars.return_value = iter([r1, r2])
        assert repo.get_for_application(uuid4()) == [r1, r2]

    def test_returns_empty_list(self) -> None:
        repo, session = _make_repo()
        session.scalars.return_value = iter([])
        assert repo.get_for_application(uuid4()) == []


class TestCountByTypeAndStatus:
    def test_returns_grouped_rows(self) -> None:
        repo, session = _make_repo()
        session.execute.return_value.all.return_value = [
            ("DOCUMENT_INGESTION", "PENDING", 3),
            ("FINDING_GENERATION", "FAILED", 1),
        ]
        rows = repo.count_by_type_and_status(uuid4())
        assert rows == [("DOCUMENT_INGESTION", "PENDING", 3), ("FINDING_GENERATION", "FAILED", 1)]

    def test_returns_empty_list(self) -> None:
        repo, session = _make_repo()
        session.execute.return_value.all.return_value = []
        assert repo.count_by_type_and_status(uuid4()) == []


class TestGetPoisonSteps:
    def test_returns_list(self) -> None:
        repo, session = _make_repo()
        session.scalars.return_value = iter(["step1", "step2"])
        assert repo.get_poison_steps(uuid4()) == ["step1", "step2"]

    def test_returns_empty_list(self) -> None:
        repo, session = _make_repo()
        session.scalars.return_value = iter([])
        assert repo.get_poison_steps(uuid4()) == []
