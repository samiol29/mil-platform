"""Unit tests for mil.document.repository — DocumentRepository."""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock
from uuid import uuid4

from mil.audit.writer import AuditWriter
from mil.document.models import Document
from mil.document.repository import DocumentRepository
from mil.kernel.security import AuthenticatedUser, Role
from mil.kernel.types import TenantId, UserId

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_CONTENT = b"sample mortgage document bytes"
_SAMPLE_HASH = hashlib.sha256(_SAMPLE_CONTENT).hexdigest()
_SAMPLE_REFERENCE = "/tmp/mil-local-storage/sample.bin"


def _make_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=UserId(uuid4()),
        tenant_id=TenantId(uuid4()),
        roles=frozenset({Role.RELATIONSHIP_MANAGER}),
    )


def _make_document(application_id=None) -> Document:
    return Document.create(
        tenant_id=uuid4(),
        application_id=application_id or uuid4(),
        uploaded_by=uuid4(),
        original_filename="payslip.pdf",
        mime_type="application/pdf",
        size_bytes=len(_SAMPLE_CONTENT),
        content_hash=_SAMPLE_HASH,
        storage_reference=_SAMPLE_REFERENCE,
    )


def _make_repo() -> tuple[DocumentRepository, MagicMock, MagicMock]:
    session = MagicMock()
    audit_writer = MagicMock(spec=AuditWriter)
    return DocumentRepository(session, audit_writer), session, audit_writer


# ---------------------------------------------------------------------------
# save()
# ---------------------------------------------------------------------------


class TestRepositorySave:
    def test_save_adds_document_to_session(self) -> None:
        repo, session, _ = _make_repo()
        doc = _make_document()
        user = _make_user()
        repo.save(doc, actor=user)
        session.add.assert_called_once_with(doc)

    def test_save_calls_flush(self) -> None:
        repo, session, _ = _make_repo()
        doc = _make_document()
        repo.save(doc, actor=_make_user())
        session.flush.assert_called_once()

    def test_save_emits_document_uploaded_audit_event(self) -> None:
        repo, _, audit = _make_repo()
        doc = _make_document()
        repo.save(doc, actor=_make_user())
        event_types = [c.kwargs["event_type"] for c in audit.record.call_args_list]
        assert "DOCUMENT_UPLOADED" in event_types

    def test_save_emits_document_stored_audit_event(self) -> None:
        repo, _, audit = _make_repo()
        doc = _make_document()
        repo.save(doc, actor=_make_user())
        event_types = [c.kwargs["event_type"] for c in audit.record.call_args_list]
        assert "DOCUMENT_STORED" in event_types

    def test_save_emits_two_audit_events_on_create(self) -> None:
        repo, _, audit = _make_repo()
        doc = _make_document()
        repo.save(doc, actor=_make_user())
        assert audit.record.call_count == 2

    def test_save_audit_event_has_correct_entity_type(self) -> None:
        repo, _, audit = _make_repo()
        doc = _make_document()
        repo.save(doc, actor=_make_user())
        for call in audit.record.call_args_list:
            assert call.kwargs["entity_type"] == "DOCUMENT"

    def test_save_audit_event_has_actor_id(self) -> None:
        repo, _, audit = _make_repo()
        doc = _make_document()
        user = _make_user()
        repo.save(doc, actor=user)
        for call in audit.record.call_args_list:
            assert call.kwargs["actor_id"] == user.user_id

    def test_save_audit_event_has_tenant_id(self) -> None:
        repo, _, audit = _make_repo()
        doc = _make_document()
        repo.save(doc, actor=_make_user())
        for call in audit.record.call_args_list:
            assert call.kwargs["tenant_id"] == doc.tenant_id

    def test_save_audit_event_has_application_id(self) -> None:
        repo, _, audit = _make_repo()
        app_id = uuid4()
        doc = _make_document(application_id=app_id)
        repo.save(doc, actor=_make_user())
        for call in audit.record.call_args_list:
            assert call.kwargs["application_id"] == app_id

    def test_save_clears_pending_events_after_flush(self) -> None:
        repo, _, _ = _make_repo()
        doc = _make_document()
        repo.save(doc, actor=_make_user())
        assert doc.collect_pending_events() == []

    def test_save_with_no_events_calls_no_audit_records(self) -> None:
        repo, _, audit = _make_repo()
        doc = _make_document()
        doc.collect_pending_events()  # drain events before save
        repo.save(doc, actor=_make_user())
        audit.record.assert_not_called()

    def test_save_second_time_after_mark_failed_emits_failed_event(self) -> None:
        repo, _, audit = _make_repo()
        doc = _make_document()
        doc.collect_pending_events()  # drain upload/stored events
        doc.mark_failed("provider error")
        repo.save(doc, actor=_make_user())
        event_types = [c.kwargs["event_type"] for c in audit.record.call_args_list]
        assert "DOCUMENT_INGESTION_FAILED" in event_types


# ---------------------------------------------------------------------------
# get_by_id()
# ---------------------------------------------------------------------------


class TestRepositoryGetById:
    def test_get_by_id_calls_session_get(self) -> None:
        repo, session, _ = _make_repo()
        doc_id = uuid4()
        repo.get_by_id(doc_id)
        session.get.assert_called_once_with(Document, doc_id)

    def test_get_by_id_returns_none_when_not_found(self) -> None:
        repo, session, _ = _make_repo()
        session.get.return_value = None
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_id_returns_document_when_found(self) -> None:
        repo, session, _ = _make_repo()
        doc = _make_document()
        session.get.return_value = doc
        assert repo.get_by_id(doc.id) is doc

    def test_exists_returns_false_when_not_found(self) -> None:
        repo, session, _ = _make_repo()
        session.get.return_value = None
        assert repo.exists(uuid4()) is False

    def test_exists_returns_true_when_found(self) -> None:
        repo, session, _ = _make_repo()
        session.get.return_value = _make_document()
        assert repo.exists(uuid4()) is True


# ---------------------------------------------------------------------------
# get_for_application()
# ---------------------------------------------------------------------------


class TestRepositoryGetForApplication:
    def test_get_for_application_calls_scalars(self) -> None:
        repo, session, _ = _make_repo()
        session.scalars.return_value = iter([])
        result = repo.get_for_application(uuid4())
        assert result == []
        session.scalars.assert_called_once()

    def test_get_for_application_returns_list(self) -> None:
        repo, session, _ = _make_repo()
        doc1 = _make_document()
        doc2 = _make_document()
        session.scalars.return_value = iter([doc1, doc2])
        result = repo.get_for_application(uuid4())
        assert result == [doc1, doc2]


class TestRepositoryGetByApplicationAndHash:
    def test_returns_none_when_no_match(self) -> None:
        repo, session, _ = _make_repo()
        session.scalars.return_value.first.return_value = None
        result = repo.get_by_application_and_hash(uuid4(), _SAMPLE_HASH)
        assert result is None

    def test_returns_existing_document_on_match(self) -> None:
        repo, session, _ = _make_repo()
        existing = _make_document()
        session.scalars.return_value.first.return_value = existing
        result = repo.get_by_application_and_hash(existing.application_id, _SAMPLE_HASH)
        assert result is existing
