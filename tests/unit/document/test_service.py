"""Unit tests for mil.document.service — DocumentService."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from mil.document.models import Document, IngestionStatus
from mil.document.repository import DocumentRepository
from mil.document.service import DocumentService
from mil.kernel.errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from mil.kernel.event_bus import EventBus
from mil.kernel.events import DocumentIngested
from mil.kernel.providers.storage import StorageProvider, StorageReference
from mil.kernel.security import AuthenticatedUser, Role
from mil.kernel.types import TenantId, UserId

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_CONTENT = b"%PDF-1.4 sample document for unit tests"
_SAMPLE_HASH = hashlib.sha256(_SAMPLE_CONTENT).hexdigest()
_SAMPLE_REFERENCE = "/tmp/mil-local-storage/sample.bin"


def _make_user(*roles: str) -> AuthenticatedUser:
    if not roles:
        roles = (Role.RELATIONSHIP_MANAGER,)
    return AuthenticatedUser(
        user_id=UserId(uuid4()),
        tenant_id=TenantId(uuid4()),
        roles=frozenset(roles),
    )


def _make_admin() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=UserId(uuid4()),
        tenant_id=TenantId(uuid4()),
        roles=frozenset({Role.ADMIN}),
    )


def _make_storage_reference(
    reference: str = _SAMPLE_REFERENCE,
    content_hash: str = _SAMPLE_HASH,
    size_bytes: int = len(_SAMPLE_CONTENT),
) -> StorageReference:
    return StorageReference(
        reference=reference,
        content_hash=content_hash,
        size_bytes=size_bytes,
        stored_at=datetime.now(UTC),
    )


def _make_service() -> tuple[DocumentService, MagicMock, MagicMock, MagicMock]:
    repo = MagicMock(spec=DocumentRepository)
    storage = MagicMock(spec=StorageProvider)
    event_bus = MagicMock(spec=EventBus)
    storage.store.return_value = _make_storage_reference()
    repo.get_by_application_and_hash.return_value = None
    return DocumentService(repo, storage, event_bus), repo, storage, event_bus


# ---------------------------------------------------------------------------
# ingest_document — happy path
# ---------------------------------------------------------------------------


class TestIngestDocument:
    def test_returns_document(self) -> None:
        service, _, _, _ = _make_service()
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        doc = service.ingest_document(
            user,
            application_id=uuid4(),
            content=_SAMPLE_CONTENT,
            original_filename="payslip.pdf",
            mime_type="application/pdf",
        )
        assert isinstance(doc, Document)

    def test_document_has_pending_status(self) -> None:
        service, _, _, _ = _make_service()
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        doc = service.ingest_document(
            user,
            application_id=uuid4(),
            content=_SAMPLE_CONTENT,
            original_filename="payslip.pdf",
            mime_type="application/pdf",
        )
        assert doc.ingestion_status == IngestionStatus.PENDING

    def test_sha256_computed_correctly(self) -> None:
        service, _, storage, _ = _make_service()
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        service.ingest_document(
            user,
            application_id=uuid4(),
            content=_SAMPLE_CONTENT,
            original_filename="payslip.pdf",
            mime_type="application/pdf",
        )
        # storage.store() must receive the correct hash
        called_hash = storage.store.call_args[0][1]
        assert called_hash == _SAMPLE_HASH

    def test_storage_provider_called_with_content_and_hash(self) -> None:
        service, _, storage, _ = _make_service()
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        service.ingest_document(
            user,
            application_id=uuid4(),
            content=_SAMPLE_CONTENT,
            original_filename="payslip.pdf",
            mime_type="application/pdf",
        )
        storage.store.assert_called_once_with(_SAMPLE_CONTENT, _SAMPLE_HASH)

    def test_repository_save_called(self) -> None:
        service, repo, _, _ = _make_service()
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        service.ingest_document(
            user,
            application_id=uuid4(),
            content=_SAMPLE_CONTENT,
            original_filename="payslip.pdf",
            mime_type="application/pdf",
        )
        repo.save.assert_called_once()

    def test_document_ingested_event_published(self) -> None:
        service, _, _, event_bus = _make_service()
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        service.ingest_document(
            user,
            application_id=uuid4(),
            content=_SAMPLE_CONTENT,
            original_filename="payslip.pdf",
            mime_type="application/pdf",
        )
        event_bus.publish.assert_called_once()
        published_event = event_bus.publish.call_args[0][0]
        assert isinstance(published_event, DocumentIngested)

    def test_published_event_has_correct_content_hash(self) -> None:
        service, _, _, event_bus = _make_service()
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        service.ingest_document(
            user,
            application_id=uuid4(),
            content=_SAMPLE_CONTENT,
            original_filename="payslip.pdf",
            mime_type="application/pdf",
        )
        event = event_bus.publish.call_args[0][0]
        assert event.content_hash == _SAMPLE_HASH

    def test_published_event_has_correct_storage_reference(self) -> None:
        service, _, _, event_bus = _make_service()
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        service.ingest_document(
            user,
            application_id=uuid4(),
            content=_SAMPLE_CONTENT,
            original_filename="payslip.pdf",
            mime_type="application/pdf",
        )
        event = event_bus.publish.call_args[0][0]
        assert event.storage_reference == _SAMPLE_REFERENCE

    def test_published_event_has_correct_tenant_id(self) -> None:
        service, _, _, event_bus = _make_service()
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        service.ingest_document(
            user,
            application_id=uuid4(),
            content=_SAMPLE_CONTENT,
            original_filename="payslip.pdf",
            mime_type="application/pdf",
        )
        event = event_bus.publish.call_args[0][0]
        assert event.tenant_id == user.tenant_id

    def test_document_original_filename_stored(self) -> None:
        service, _, _, _ = _make_service()
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        doc = service.ingest_document(
            user,
            application_id=uuid4(),
            content=_SAMPLE_CONTENT,
            original_filename="bank_statement.pdf",
            mime_type="application/pdf",
        )
        assert doc.original_filename == "bank_statement.pdf"

    def test_document_with_party_id(self) -> None:
        service, _, _, _ = _make_service()
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        party_id = uuid4()
        doc = service.ingest_document(
            user,
            application_id=uuid4(),
            content=_SAMPLE_CONTENT,
            original_filename="payslip.pdf",
            mime_type="application/pdf",
            party_id=party_id,
        )
        assert doc.party_id == party_id

    def test_document_content_hash_matches_sha256(self) -> None:
        service, _, _, _ = _make_service()
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        content = b"unique content bytes for hash test"
        expected_hash = hashlib.sha256(content).hexdigest()
        service._storage.store.return_value = _make_storage_reference(content_hash=expected_hash)
        doc = service.ingest_document(
            user,
            application_id=uuid4(),
            content=content,
            original_filename="doc.pdf",
            mime_type="application/pdf",
        )
        assert doc.content_hash == expected_hash


# ---------------------------------------------------------------------------
# ingest_document — RBAC enforcement
# ---------------------------------------------------------------------------


class TestIngestDocumentRBAC:
    def test_upload_document_permission_required(self) -> None:
        service, _, _, _ = _make_service()
        # RISK_ANALYST has no upload:document permission
        user = AuthenticatedUser(
            user_id=UserId(uuid4()),
            tenant_id=TenantId(uuid4()),
            roles=frozenset({Role.RISK_ANALYST}),
        )
        with pytest.raises(AuthorizationError):
            service.ingest_document(
                user,
                application_id=uuid4(),
                content=_SAMPLE_CONTENT,
                original_filename="payslip.pdf",
                mime_type="application/pdf",
            )

    def test_relationship_manager_can_upload(self) -> None:
        service, _, _, _ = _make_service()
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        doc = service.ingest_document(
            user,
            application_id=uuid4(),
            content=_SAMPLE_CONTENT,
            original_filename="payslip.pdf",
            mime_type="application/pdf",
        )
        assert doc is not None

    def test_admin_can_upload(self) -> None:
        service, _, _, _ = _make_service()
        user = _make_admin()
        doc = service.ingest_document(
            user,
            application_id=uuid4(),
            content=_SAMPLE_CONTENT,
            original_filename="payslip.pdf",
            mime_type="application/pdf",
        )
        assert doc is not None

    def test_storage_not_called_when_no_permission(self) -> None:
        service, _, storage, _ = _make_service()
        user = AuthenticatedUser(
            user_id=UserId(uuid4()),
            tenant_id=TenantId(uuid4()),
            roles=frozenset({Role.AUDIT_TEAM}),
        )
        with pytest.raises(AuthorizationError):
            service.ingest_document(
                user,
                application_id=uuid4(),
                content=_SAMPLE_CONTENT,
                original_filename="payslip.pdf",
                mime_type="application/pdf",
            )
        storage.store.assert_not_called()


# ---------------------------------------------------------------------------
# ingest_document — validation
# ---------------------------------------------------------------------------


class TestIngestDocumentDuplicateDetection:
    """
    A real gap found via live end-to-end testing: without this check,
    re-uploading the same file bytes to the same application created a
    second ``Document`` row with its own ``document_id`` — the pipeline's
    replay-safety (keyed on ``document_id``, not content) never recognized
    it as a duplicate, so OCR and Extraction ran again and doubled the
    application's evidence pool.
    """

    def test_raises_conflict_for_byte_identical_reupload(self) -> None:
        service, repo, _, _ = _make_service()
        application_id = uuid4()
        existing = Document.create(
            tenant_id=uuid4(),
            application_id=application_id,
            uploaded_by=uuid4(),
            original_filename="payslip.pdf",
            mime_type="application/pdf",
            size_bytes=len(_SAMPLE_CONTENT),
            content_hash=_SAMPLE_HASH,
            storage_reference=_SAMPLE_REFERENCE,
        )
        repo.get_by_application_and_hash.return_value = existing
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        with pytest.raises(ConflictError):
            service.ingest_document(
                user,
                application_id=application_id,
                content=_SAMPLE_CONTENT,
                original_filename="payslip-again.pdf",
                mime_type="application/pdf",
            )

    def test_does_not_call_storage_or_publish_event_on_duplicate(self) -> None:
        service, repo, storage, event_bus = _make_service()
        application_id = uuid4()
        existing = Document.create(
            tenant_id=uuid4(),
            application_id=application_id,
            uploaded_by=uuid4(),
            original_filename="payslip.pdf",
            mime_type="application/pdf",
            size_bytes=len(_SAMPLE_CONTENT),
            content_hash=_SAMPLE_HASH,
            storage_reference=_SAMPLE_REFERENCE,
        )
        repo.get_by_application_and_hash.return_value = existing
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        with pytest.raises(ConflictError):
            service.ingest_document(
                user,
                application_id=application_id,
                content=_SAMPLE_CONTENT,
                original_filename="payslip-again.pdf",
                mime_type="application/pdf",
            )
        storage.store.assert_not_called()
        repo.save.assert_not_called()
        event_bus.publish.assert_not_called()

    def test_checks_duplicate_scoped_to_application_and_hash(self) -> None:
        service, repo, _, _ = _make_service()
        application_id = uuid4()
        service.ingest_document(
            _make_user(Role.RELATIONSHIP_MANAGER),
            application_id=application_id,
            content=_SAMPLE_CONTENT,
            original_filename="payslip.pdf",
            mime_type="application/pdf",
        )
        repo.get_by_application_and_hash.assert_called_once_with(application_id, _SAMPLE_HASH)

    def test_different_content_to_same_application_is_not_a_duplicate(self) -> None:
        """A corrected re-scan (different bytes) must not be rejected."""
        service, repo, _, _ = _make_service()
        repo.get_by_application_and_hash.return_value = None
        result = service.ingest_document(
            _make_user(Role.RELATIONSHIP_MANAGER),
            application_id=uuid4(),
            content=_SAMPLE_CONTENT,
            original_filename="payslip.pdf",
            mime_type="application/pdf",
        )
        assert result is not None


class TestIngestDocumentValidation:
    def test_empty_content_raises(self) -> None:
        service, _, _, _ = _make_service()
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        with pytest.raises(ValidationError):
            service.ingest_document(
                user,
                application_id=uuid4(),
                content=b"",
                original_filename="empty.pdf",
                mime_type="application/pdf",
            )


# ---------------------------------------------------------------------------
# get_document
# ---------------------------------------------------------------------------


class TestGetDocument:
    def test_returns_document_when_found(self) -> None:
        service, repo, _, _ = _make_service()
        doc = Document.create(
            tenant_id=uuid4(),
            application_id=uuid4(),
            uploaded_by=uuid4(),
            original_filename="payslip.pdf",
            mime_type="application/pdf",
            size_bytes=100,
            content_hash=_SAMPLE_HASH,
            storage_reference=_SAMPLE_REFERENCE,
        )
        repo.get_by_id.return_value = doc
        user = _make_user(Role.VERIFICATION_OFFICER)
        result = service.get_document(user, document_id=doc.id)
        assert result is doc

    def test_raises_not_found_when_missing(self) -> None:
        service, repo, _, _ = _make_service()
        repo.get_by_id.return_value = None
        user = _make_user(Role.VERIFICATION_OFFICER)
        with pytest.raises(NotFoundError, match="Document"):
            service.get_document(user, document_id=uuid4())

    def test_requires_read_document_permission(self) -> None:
        service, _, _, _ = _make_service()
        user = AuthenticatedUser(
            user_id=UserId(uuid4()),
            tenant_id=TenantId(uuid4()),
            roles=frozenset({Role.OPERATIONS_MANAGER}),
        )
        with pytest.raises(AuthorizationError):
            service.get_document(user, document_id=uuid4())


# ---------------------------------------------------------------------------
# retry_ingestion
# ---------------------------------------------------------------------------


class TestRetryIngestion:
    def _make_failed_document(self) -> Document:
        doc = Document.create(
            tenant_id=uuid4(),
            application_id=uuid4(),
            uploaded_by=uuid4(),
            original_filename="payslip.pdf",
            mime_type="application/pdf",
            size_bytes=100,
            content_hash=_SAMPLE_HASH,
            storage_reference=_SAMPLE_REFERENCE,
        )
        doc.mark_failed("provider unavailable")
        doc.collect_pending_events()
        return doc

    def test_resets_failed_document_to_pending(self) -> None:
        service, repo, _, _ = _make_service()
        doc = self._make_failed_document()
        repo.get_by_id.return_value = doc
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        result = service.retry_ingestion(user, document_id=doc.id)
        assert result.ingestion_status == IngestionStatus.PENDING

    def test_increments_retry_count(self) -> None:
        service, repo, _, _ = _make_service()
        doc = self._make_failed_document()
        repo.get_by_id.return_value = doc
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        result = service.retry_ingestion(user, document_id=doc.id)
        assert result.retry_count == 1

    def test_saves_with_user_actor(self) -> None:
        service, repo, _, _ = _make_service()
        doc = self._make_failed_document()
        repo.get_by_id.return_value = doc
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        service.retry_ingestion(user, document_id=doc.id)
        repo.save.assert_called_once()
        assert repo.save.call_args.kwargs["actor"] is user

    def test_raises_not_found_when_missing(self) -> None:
        service, repo, _, _ = _make_service()
        repo.get_by_id.return_value = None
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        with pytest.raises(NotFoundError, match="Document"):
            service.retry_ingestion(user, document_id=uuid4())

    def test_raises_conflict_when_not_failed(self) -> None:
        service, repo, _, _ = _make_service()
        doc = Document.create(
            tenant_id=uuid4(),
            application_id=uuid4(),
            uploaded_by=uuid4(),
            original_filename="payslip.pdf",
            mime_type="application/pdf",
            size_bytes=100,
            content_hash=_SAMPLE_HASH,
            storage_reference=_SAMPLE_REFERENCE,
        )
        repo.get_by_id.return_value = doc
        user = _make_user(Role.RELATIONSHIP_MANAGER)
        with pytest.raises(ConflictError):
            service.retry_ingestion(user, document_id=doc.id)

    def test_requires_upload_document_permission(self) -> None:
        service, repo, _, _ = _make_service()
        doc = self._make_failed_document()
        repo.get_by_id.return_value = doc
        user = AuthenticatedUser(
            user_id=UserId(uuid4()),
            tenant_id=TenantId(uuid4()),
            roles=frozenset({Role.RISK_ANALYST}),
        )
        with pytest.raises(AuthorizationError):
            service.retry_ingestion(user, document_id=doc.id)


# ---------------------------------------------------------------------------
# list_documents
# ---------------------------------------------------------------------------


class TestListDocuments:
    def test_returns_list(self) -> None:
        service, repo, _, _ = _make_service()
        repo.get_for_application.return_value = []
        user = _make_user(Role.VERIFICATION_OFFICER)
        result = service.list_documents(user, application_id=uuid4())
        assert result == []

    def test_requires_read_document_permission(self) -> None:
        service, _, _, _ = _make_service()
        user = AuthenticatedUser(
            user_id=UserId(uuid4()),
            tenant_id=TenantId(uuid4()),
            roles=frozenset({Role.OPERATIONS_MANAGER}),
        )
        with pytest.raises(AuthorizationError):
            service.list_documents(user, application_id=uuid4())


# ---------------------------------------------------------------------------
# compute_content_hash utility
# ---------------------------------------------------------------------------


class TestComputeContentHash:
    def test_matches_sha256(self) -> None:
        content = b"mortgage document bytes"
        expected = hashlib.sha256(content).hexdigest()
        assert DocumentService.compute_content_hash(content) == expected

    def test_returns_64_char_hex(self) -> None:
        result = DocumentService.compute_content_hash(b"test")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_different_content_produces_different_hash(self) -> None:
        h1 = DocumentService.compute_content_hash(b"document A")
        h2 = DocumentService.compute_content_hash(b"document B")
        assert h1 != h2

    def test_same_content_produces_same_hash(self) -> None:
        content = b"deterministic content"
        assert DocumentService.compute_content_hash(
            content
        ) == DocumentService.compute_content_hash(content)
