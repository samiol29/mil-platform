"""Unit tests for mil.evidence.repository — EvidenceRepository."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from mil.evidence.models import EvidenceItem
from mil.evidence.repository import EvidenceRepository
from mil.kernel.providers.extraction import EvidenceAttributes


def _attrs() -> EvidenceAttributes:
    return EvidenceAttributes(
        field_name="gross_monthly_income",
        field_value="5000.00",
        document_id="doc-1",
        source_document_ref="ref-1",
        page_number=1,
        field_location=None,
        extraction_confidence=0.85,
        extraction_method="mock-keyword-matcher",
        extracted_at=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
        extraction_version="mock-extraction-1.0.0",
    )


def _item() -> EvidenceItem:
    return EvidenceItem.create(
        application_id=uuid4(),
        document_id=uuid4(),
        workflow_run_id=uuid4(),
        tenant_id=uuid4(),
        attrs=_attrs(),
    )


def _make_repo() -> tuple[EvidenceRepository, MagicMock]:
    session = MagicMock()
    return EvidenceRepository(session), session


class TestSave:
    def test_adds_and_flushes(self) -> None:
        repo, session = _make_repo()
        item = _item()
        repo.save(item)
        session.add.assert_called_once_with(item)
        session.flush.assert_called_once()

    def test_does_not_commit(self) -> None:
        repo, session = _make_repo()
        repo.save(_item())
        session.commit.assert_not_called()


class TestSaveIfNotExists:
    def test_returns_true_and_adds_on_success(self) -> None:
        repo, session = _make_repo()
        # A real `session.begin_nested()` (SAVEPOINT) used as a context
        # manager does not suppress exceptions on `__exit__` (it rolls back
        # and re-raises); the default MagicMock `__exit__` return value is
        # truthy, which would incorrectly *suppress* an exception, so it
        # must be forced to `False` to faithfully emulate that behavior.
        session.begin_nested.return_value.__exit__.return_value = False
        item = _item()
        assert repo.save_if_not_exists(item) is True
        session.add.assert_called_once_with(item)
        session.flush.assert_called_once()

    def test_returns_false_on_integrity_error_without_raising(self) -> None:
        repo, session = _make_repo()
        session.begin_nested.return_value.__exit__.return_value = False
        session.flush.side_effect = IntegrityError("INSERT", {}, Exception("duplicate key"))
        # Must not raise: ADR-008 §5 treats this as proof of a prior commit.
        assert repo.save_if_not_exists(_item()) is False


class TestExistsForDocumentAndVersion:
    def test_true_when_present(self) -> None:
        repo, session = _make_repo()
        session.scalars.return_value.first.return_value = uuid4()
        assert repo.exists_for_document_and_version(uuid4(), "mock-extraction-1.0.0") is True

    def test_false_when_absent(self) -> None:
        repo, session = _make_repo()
        session.scalars.return_value.first.return_value = None
        assert repo.exists_for_document_and_version(uuid4(), "mock-extraction-1.0.0") is False


class TestGetForDocument:
    def test_returns_list(self) -> None:
        repo, session = _make_repo()
        i1, i2 = _item(), _item()
        session.scalars.return_value = iter([i1, i2])
        assert repo.get_for_document(uuid4()) == [i1, i2]


class TestGetForApplication:
    def test_returns_list(self) -> None:
        repo, session = _make_repo()
        i1, i2 = _item(), _item()
        session.scalars.return_value = iter([i1, i2])
        assert repo.get_for_application(uuid4()) == [i1, i2]


class TestCountForTenant:
    def test_returns_count(self) -> None:
        repo, session = _make_repo()
        session.scalars.return_value.one.return_value = 7
        assert repo.count_for_tenant(uuid4()) == 7
