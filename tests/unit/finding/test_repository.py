"""Unit tests for mil.finding.repository — FindingRepository."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from mil.finding.models import Finding
from mil.finding.repository import FindingRepository


def _finding() -> Finding:
    return Finding.create(
        application_id=uuid4(),
        tenant_id=uuid4(),
        workflow_run_id=uuid4(),
        finding_type="AI_GENERATED_ASSESSMENT",
        title="T",
        rationale="R",
        evidence_summary="ES",
        confidence_label="HIGH",
        recommended_action="RA",
        confidence_score=Decimal("0.900"),
        model_version="mock-inference-1.0.0",
        prompt_version="finding-generation-prompt-v1",
        extraction_version="mock-extraction-1.0.0",
        evidence_item_ids=[uuid4()],
        generated_at=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
    )


def _make_repo() -> tuple[FindingRepository, MagicMock]:
    session = MagicMock()
    return FindingRepository(session), session


class TestSave:
    def test_adds_and_flushes(self) -> None:
        repo, session = _make_repo()
        finding = _finding()
        repo.save(finding)
        session.add.assert_called_once_with(finding)
        session.flush.assert_called_once()

    def test_does_not_commit(self) -> None:
        repo, session = _make_repo()
        repo.save(_finding())
        session.commit.assert_not_called()


class TestExistsForApplicationAndVersion:
    def test_true_when_present(self) -> None:
        repo, session = _make_repo()
        session.scalars.return_value.first.return_value = uuid4()
        assert repo.exists_for_application_and_version(uuid4(), "mock-inference-1.0.0") is True

    def test_false_when_absent(self) -> None:
        repo, session = _make_repo()
        session.scalars.return_value.first.return_value = None
        assert repo.exists_for_application_and_version(uuid4(), "mock-inference-1.0.0") is False


class TestGetForApplication:
    def test_returns_list(self) -> None:
        repo, session = _make_repo()
        f1, f2 = _finding(), _finding()
        session.scalars.return_value = iter([f1, f2])
        assert repo.get_for_application(uuid4()) == [f1, f2]
