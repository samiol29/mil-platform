"""Unit tests for mil.document.models — IngestionStatus, Document."""

from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest

from mil.document.models import Document, IngestionStatus
from mil.kernel.errors import ConflictError, ValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_CONTENT = b"%PDF-1.4 sample mortgage document"
_SAMPLE_HASH = hashlib.sha256(_SAMPLE_CONTENT).hexdigest()
_SAMPLE_REFERENCE = "local:/tmp/mil-local-storage/sample.bin"


def _make_document(
    *,
    original_filename: str = "income_statement.pdf",
    mime_type: str = "application/pdf",
    size_bytes: int = len(_SAMPLE_CONTENT),
    content_hash: str = _SAMPLE_HASH,
    storage_reference: str = _SAMPLE_REFERENCE,
    party_id=None,
) -> Document:
    return Document.create(
        tenant_id=uuid4(),
        application_id=uuid4(),
        uploaded_by=uuid4(),
        original_filename=original_filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
        content_hash=content_hash,
        storage_reference=storage_reference,
        party_id=party_id,
    )


# ---------------------------------------------------------------------------
# IngestionStatus
# ---------------------------------------------------------------------------


class TestIngestionStatus:
    def test_all_expected_statuses(self) -> None:
        expected = {"PENDING", "IN_PROGRESS", "COMPLETED", "FAILED"}
        assert {s.value for s in IngestionStatus} == expected

    def test_members_are_strings(self) -> None:
        for status in IngestionStatus:
            assert isinstance(status, str)

    def test_lookup_by_value(self) -> None:
        assert IngestionStatus("PENDING") is IngestionStatus.PENDING
        assert IngestionStatus("COMPLETED") is IngestionStatus.COMPLETED

    def test_is_str_subtype(self) -> None:
        assert issubclass(IngestionStatus, str)


# ---------------------------------------------------------------------------
# Document.create — factory and basic properties
# ---------------------------------------------------------------------------


class TestDocumentCreate:
    def test_returns_document(self) -> None:
        assert isinstance(_make_document(), Document)

    def test_initial_status_is_pending(self) -> None:
        doc = _make_document()
        assert doc.ingestion_status == IngestionStatus.PENDING

    def test_id_is_uuid(self) -> None:
        from uuid import UUID

        doc = _make_document()
        assert isinstance(doc.id, UUID)

    def test_two_documents_have_different_ids(self) -> None:
        assert _make_document().id != _make_document().id

    def test_content_hash_stored(self) -> None:
        doc = _make_document(content_hash=_SAMPLE_HASH)
        assert doc.content_hash == _SAMPLE_HASH

    def test_storage_reference_stored(self) -> None:
        doc = _make_document(storage_reference=_SAMPLE_REFERENCE)
        assert doc.storage_reference == _SAMPLE_REFERENCE

    def test_original_filename_stored(self) -> None:
        doc = _make_document(original_filename="bank_statement.pdf")
        assert doc.original_filename == "bank_statement.pdf"

    def test_original_filename_stripped(self) -> None:
        doc = _make_document(original_filename="  payslip.pdf  ")
        assert doc.original_filename == "payslip.pdf"

    def test_mime_type_stored(self) -> None:
        doc = _make_document(mime_type="image/jpeg")
        assert doc.mime_type == "image/jpeg"

    def test_mime_type_stripped(self) -> None:
        doc = _make_document(mime_type="  application/pdf  ")
        assert doc.mime_type == "application/pdf"

    def test_size_bytes_stored(self) -> None:
        doc = _make_document(size_bytes=4096)
        assert doc.size_bytes == 4096

    def test_uploaded_at_is_timezone_aware(self) -> None:
        doc = _make_document()
        assert doc.uploaded_at.tzinfo is not None

    def test_party_id_optional(self) -> None:
        doc = _make_document()
        assert doc.party_id is None

    def test_party_id_stored(self) -> None:
        pid = uuid4()
        doc = _make_document(party_id=pid)
        assert doc.party_id == pid

    def test_is_pending_property(self) -> None:
        doc = _make_document()
        assert doc.is_pending is True
        assert doc.is_completed is False

    def test_repr_contains_status_and_hash(self) -> None:
        doc = _make_document()
        r = repr(doc)
        assert "Document" in r
        assert "PENDING" in r


# ---------------------------------------------------------------------------
# Document.create — validation
# ---------------------------------------------------------------------------


class TestDocumentCreateValidation:
    def test_empty_original_filename_raises(self) -> None:
        with pytest.raises(ValidationError, match="original_filename"):
            _make_document(original_filename="")

    def test_whitespace_original_filename_raises(self) -> None:
        with pytest.raises(ValidationError, match="original_filename"):
            _make_document(original_filename="   ")

    def test_empty_mime_type_raises(self) -> None:
        with pytest.raises(ValidationError, match="mime_type"):
            _make_document(mime_type="")

    def test_negative_size_bytes_raises(self) -> None:
        with pytest.raises(ValidationError, match="size_bytes"):
            _make_document(size_bytes=-1)

    def test_empty_content_hash_raises(self) -> None:
        with pytest.raises(ValidationError, match="content_hash"):
            _make_document(content_hash="")

    def test_short_content_hash_raises(self) -> None:
        with pytest.raises(ValidationError, match="content_hash"):
            _make_document(content_hash="abc123")

    def test_wrong_length_content_hash_raises(self) -> None:
        with pytest.raises(ValidationError, match="content_hash"):
            _make_document(content_hash="a" * 63)

    def test_valid_64_char_hash_accepted(self) -> None:
        doc = _make_document(content_hash="b" * 64)
        assert doc.content_hash == "b" * 64

    def test_empty_storage_reference_raises(self) -> None:
        with pytest.raises(ValidationError, match="storage_reference"):
            _make_document(storage_reference="")

    def test_whitespace_storage_reference_raises(self) -> None:
        with pytest.raises(ValidationError, match="storage_reference"):
            _make_document(storage_reference="   ")

    def test_zero_size_bytes_allowed(self) -> None:
        doc = _make_document(size_bytes=0)
        assert doc.size_bytes == 0


# ---------------------------------------------------------------------------
# Document pending events
# ---------------------------------------------------------------------------


class TestDocumentPendingEvents:
    def test_create_enqueues_document_uploaded_event(self) -> None:
        doc = _make_document()
        events = doc.collect_pending_events()
        event_types = [e["event_type"] for e in events]
        assert "DOCUMENT_UPLOADED" in event_types

    def test_create_enqueues_document_stored_event(self) -> None:
        doc = _make_document()
        events = doc.collect_pending_events()
        event_types = [e["event_type"] for e in events]
        assert "DOCUMENT_STORED" in event_types

    def test_create_enqueues_two_events(self) -> None:
        doc = _make_document()
        events = doc.collect_pending_events()
        assert len(events) == 2

    def test_document_uploaded_event_has_correct_entity_type(self) -> None:
        doc = _make_document()
        events = doc.collect_pending_events()
        uploaded = next(e for e in events if e["event_type"] == "DOCUMENT_UPLOADED")
        assert uploaded["entity_type"] == "DOCUMENT"

    def test_document_uploaded_event_references_document_id(self) -> None:
        doc = _make_document()
        events = doc.collect_pending_events()
        uploaded = next(e for e in events if e["event_type"] == "DOCUMENT_UPLOADED")
        assert uploaded["entity_id"] == doc.id

    def test_document_stored_event_includes_storage_reference(self) -> None:
        doc = _make_document(storage_reference=_SAMPLE_REFERENCE)
        events = doc.collect_pending_events()
        stored = next(e for e in events if e["event_type"] == "DOCUMENT_STORED")
        data = stored["data"]
        assert data["storage_reference"] == _SAMPLE_REFERENCE  # type: ignore[index]

    def test_collect_clears_queue(self) -> None:
        doc = _make_document()
        doc.collect_pending_events()
        assert doc.collect_pending_events() == []

    def test_document_uploaded_data_includes_content_hash(self) -> None:
        doc = _make_document(content_hash=_SAMPLE_HASH)
        events = doc.collect_pending_events()
        uploaded = next(e for e in events if e["event_type"] == "DOCUMENT_UPLOADED")
        assert uploaded["data"]["content_hash"] == _SAMPLE_HASH  # type: ignore[index]


# ---------------------------------------------------------------------------
# Document status transitions
# ---------------------------------------------------------------------------


class TestDocumentStatusTransitions:
    def test_mark_processing_from_pending(self) -> None:
        doc = _make_document()
        doc.mark_processing()
        assert doc.ingestion_status == IngestionStatus.IN_PROGRESS

    def test_mark_processing_from_non_pending_raises(self) -> None:
        doc = _make_document()
        doc.mark_processing()
        with pytest.raises(ConflictError):
            doc.mark_processing()

    def test_mark_completed_from_in_progress(self) -> None:
        doc = _make_document()
        doc.mark_processing()
        doc.mark_completed(page_count=2, evidence_item_count=5)
        assert doc.ingestion_status == IngestionStatus.COMPLETED

    def test_mark_completed_populates_pipeline_outcome_fields(self) -> None:
        doc = _make_document()
        doc.mark_processing()
        doc.mark_completed(page_count=3, evidence_item_count=7)
        assert doc.page_count == 3
        assert doc.evidence_item_count == 7
        assert doc.ingestion_completed_at is not None

    def test_mark_failed_populates_ingestion_error(self) -> None:
        doc = _make_document()
        doc.mark_failed("provider unavailable")
        assert doc.ingestion_error == "provider unavailable"

    def test_mark_completed_from_pending_raises(self) -> None:
        doc = _make_document()
        with pytest.raises(ConflictError):
            doc.mark_completed(page_count=2, evidence_item_count=5)

    def test_mark_failed_from_pending(self) -> None:
        doc = _make_document()
        doc.mark_failed("OCR provider unavailable")
        assert doc.ingestion_status == IngestionStatus.FAILED

    def test_mark_failed_from_in_progress(self) -> None:
        doc = _make_document()
        doc.mark_processing()
        doc.mark_failed("extraction failed")
        assert doc.ingestion_status == IngestionStatus.FAILED

    def test_mark_failed_from_completed_raises(self) -> None:
        doc = _make_document()
        doc.mark_processing()
        doc.mark_completed(page_count=2, evidence_item_count=5)
        with pytest.raises(ConflictError):
            doc.mark_failed("too late")

    def test_mark_failed_enqueues_failed_event(self) -> None:
        doc = _make_document()
        doc.collect_pending_events()  # drain upload events
        doc.mark_failed("provider error")
        events = doc.collect_pending_events()
        event_types = [e["event_type"] for e in events]
        assert "DOCUMENT_INGESTION_FAILED" in event_types

    def test_is_completed_property(self) -> None:
        doc = _make_document()
        assert not doc.is_completed
        doc.mark_processing()
        doc.mark_completed(page_count=2, evidence_item_count=5)
        assert doc.is_completed


# ---------------------------------------------------------------------------
# Document ORM metadata
# ---------------------------------------------------------------------------


class TestDocumentORMMetadata:
    def test_tablename(self) -> None:
        assert Document.__tablename__ == "documents"

    def test_schema(self) -> None:
        assert Document.__table_args__["schema"] == "core"

    def test_ingestion_status_enum_property(self) -> None:
        doc = _make_document()
        assert doc.ingestion_status_enum is IngestionStatus.PENDING
