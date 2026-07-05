"""Unit tests for DocumentService pipeline lifecycle transitions (system-driven)."""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from mil.document.models import Document, IngestionStatus
from mil.document.service import DocumentService
from mil.kernel.errors import ConflictError, NotFoundError

_CONTENT = b"document bytes"
_HASH = hashlib.sha256(_CONTENT).hexdigest()


def _make_document() -> Document:
    return Document.create(
        tenant_id=uuid4(),
        application_id=uuid4(),
        uploaded_by=uuid4(),
        original_filename="payslip.pdf",
        mime_type="application/pdf",
        size_bytes=len(_CONTENT),
        content_hash=_HASH,
        storage_reference="/tmp/mil/ref",
    )


def _make_service(document: Document | None) -> tuple[DocumentService, MagicMock]:
    repo = MagicMock()
    repo.get_by_id.return_value = document
    service = DocumentService(repo, MagicMock(), MagicMock())
    return service, repo


# ---------------------------------------------------------------------------
# start_processing
# ---------------------------------------------------------------------------


class TestStartProcessing:
    def test_transitions_pending_to_in_progress(self) -> None:
        doc = _make_document()
        service, _ = _make_service(doc)
        result = service.start_processing(document_id=doc.id)
        assert result.ingestion_status == IngestionStatus.IN_PROGRESS

    def test_saves_with_system_actor(self) -> None:
        doc = _make_document()
        service, repo = _make_service(doc)
        service.start_processing(document_id=doc.id)
        repo.save.assert_called_once()
        assert repo.save.call_args.kwargs["actor"] is None

    def test_idempotent_when_already_in_progress(self) -> None:
        doc = _make_document()
        doc.mark_processing()
        doc.collect_pending_events()
        service, repo = _make_service(doc)
        service.start_processing(document_id=doc.id)
        repo.save.assert_not_called()

    def test_not_found_raises(self) -> None:
        service, _ = _make_service(None)
        with pytest.raises(NotFoundError):
            service.start_processing(document_id=uuid4())

    def test_terminal_document_raises(self) -> None:
        doc = _make_document()
        doc.mark_processing()
        doc.mark_completed(page_count=1, evidence_item_count=1)
        service, _ = _make_service(doc)
        with pytest.raises(ConflictError):
            service.start_processing(document_id=doc.id)


# ---------------------------------------------------------------------------
# complete_processing
# ---------------------------------------------------------------------------


class TestCompleteProcessing:
    def test_transitions_in_progress_to_completed(self) -> None:
        doc = _make_document()
        doc.mark_processing()
        doc.collect_pending_events()
        service, _ = _make_service(doc)
        result = service.complete_processing(
            document_id=doc.id, page_count=4, evidence_item_count=9
        )
        assert result.ingestion_status == IngestionStatus.COMPLETED
        assert result.page_count == 4
        assert result.evidence_item_count == 9
        assert result.ingestion_completed_at is not None

    def test_idempotent_when_already_completed(self) -> None:
        doc = _make_document()
        doc.mark_processing()
        doc.mark_completed(page_count=1, evidence_item_count=1)
        doc.collect_pending_events()
        service, repo = _make_service(doc)
        service.complete_processing(document_id=doc.id, page_count=99, evidence_item_count=99)
        repo.save.assert_not_called()


# ---------------------------------------------------------------------------
# fail_processing
# ---------------------------------------------------------------------------


class TestFailProcessing:
    def test_transitions_to_failed(self) -> None:
        doc = _make_document()
        doc.mark_processing()
        doc.collect_pending_events()
        service, _ = _make_service(doc)
        result = service.fail_processing(document_id=doc.id, reason="provider down")
        assert result.ingestion_status == IngestionStatus.FAILED

    def test_saves_with_system_actor(self) -> None:
        doc = _make_document()
        service, repo = _make_service(doc)
        service.fail_processing(document_id=doc.id, reason="bad scan")
        assert repo.save.call_args.kwargs["actor"] is None

    def test_idempotent_when_already_failed(self) -> None:
        doc = _make_document()
        doc.mark_failed("first")
        doc.collect_pending_events()
        service, repo = _make_service(doc)
        service.fail_processing(document_id=doc.id, reason="second")
        repo.save.assert_not_called()


# ---------------------------------------------------------------------------
# get_for_pipeline
# ---------------------------------------------------------------------------


class TestGetForPipeline:
    def test_returns_document(self) -> None:
        doc = _make_document()
        service, _ = _make_service(doc)
        assert service.get_for_pipeline(document_id=doc.id) is doc

    def test_not_found_raises(self) -> None:
        service, _ = _make_service(None)
        with pytest.raises(NotFoundError):
            service.get_for_pipeline(document_id=uuid4())
