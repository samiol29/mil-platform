"""
DocumentService — use-case orchestrator for document ingestion.

This service owns the upload path for Sprint 3C: receive file bytes, compute
the SHA-256 content hash exactly once, delegate storage to the ``StorageProvider``
abstraction, persist the ``Document`` record, and emit the platform-level
``DocumentIngested`` ``DomainEvent`` on the ``EventBus``.

Design decisions:
- SHA-256 is computed exactly once in ``ingest_document``. The hash is passed
  through to ``StorageProvider.store()`` and to ``Document.create()``. It is
  never recomputed elsewhere.
- ``StorageProvider`` is an injected abstraction; no storage implementation
  details appear here.
- ``DocumentIngested`` is the existing Platform Kernel typed ``DomainEvent``.
  Per the sprint instructions ("Do NOT invent a second event representation"),
  this is the authoritative event for downstream consumers (Intelligence
  Orchestrator, US2).
- The two audit events (DOCUMENT_UPLOADED, DOCUMENT_STORED) are emitted via
  ``AuditWriter`` through the aggregate's pending-event queue, consistent with
  the ADR-005 transitional pattern for Sprint 3B/3C.

Dependency rule: imports only from ``mil.document``, ``mil.kernel``, and the
Python standard library. No cross-context bounded context imports.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from mil.document.models import Document
from mil.kernel.errors import ConflictError, NotFoundError
from mil.kernel.events import DocumentIngested
from mil.kernel.security import Permission, require_permission
from mil.kernel.types import ApplicationId, DocumentId

if TYPE_CHECKING:
    from uuid import UUID

    from mil.document.repository import DocumentRepository
    from mil.kernel.event_bus import EventBus
    from mil.kernel.providers.storage import StorageProvider
    from mil.kernel.security import AuthenticatedUser


class DocumentService:
    """
    Orchestrates document ingestion for the Document Processing bounded context.

    Responsibilities:
    - Enforce RBAC permissions before any operation.
    - Compute the SHA-256 content hash exactly once per uploaded file.
    - Delegate file storage to the ``StorageProvider`` abstraction.
    - Persist the ``Document`` record via ``DocumentRepository``.
    - Publish the ``DocumentIngested`` domain event on the ``EventBus``.

    ``DocumentService`` does not perform OCR, extraction, evidence generation,
    or finding generation. Those capabilities belong to US2.
    """

    def __init__(
        self,
        repository: DocumentRepository,
        storage: StorageProvider,
        event_bus: EventBus,
    ) -> None:
        self._repo = repository
        self._storage = storage
        self._event_bus = event_bus

    def ingest_document(
        self,
        user: AuthenticatedUser,
        *,
        application_id: UUID,
        content: bytes,
        original_filename: str,
        mime_type: str,
        party_id: UUID | None = None,
    ) -> Document:
        """
        Ingest a document uploaded by an authenticated user.

        The upload path:
          1. Compute SHA-256 content hash from raw bytes (exactly once).
          2. Write bytes to durable storage via ``StorageProvider``.
          3. Create ``Document`` record with PENDING status.
          4. Persist via repository — audit events DOCUMENT_UPLOADED and
             DOCUMENT_STORED are written in the same database transaction.
          5. Publish ``DocumentIngested`` on the ``EventBus`` so downstream
             consumers (Intelligence Orchestrator, US2) can react.

        Args:
            user:              Authenticated caller; must hold UPLOAD_DOCUMENT.
            application_id:    Application this document belongs to.
            content:           Raw file bytes. Must not be empty.
            original_filename: Display name for UI and audit. Business logic
                               must never depend on this value.
            mime_type:         IANA media type (e.g. "application/pdf").
            party_id:          Optional party the document pertains to.

        Returns:
            The persisted ``Document`` record in PENDING status.

        Raises:
            AuthorizationError: If the caller lacks UPLOAD_DOCUMENT permission.
            ValidationError:    If ``content`` is empty or metadata is invalid.
            ConflictError:      If this exact file (by SHA-256 content hash)
                                was already uploaded to this application —
                                see ``DocumentRepository
                                .get_by_application_and_hash``. Re-uploading
                                different bytes for the same logical document
                                (a corrected payslip, a rescan) is unaffected;
                                only a byte-for-byte duplicate is rejected.
            ProviderError:      If ``StorageProvider.store()`` fails.
        """
        require_permission(user, Permission.UPLOAD_DOCUMENT)

        if not content:
            from mil.kernel.errors import ValidationError

            raise ValidationError("Document content must not be empty", field="content")

        # SHA-256 computed exactly once — immutable for this document's lifetime.
        content_hash = hashlib.sha256(content).hexdigest()

        # Reject a byte-for-byte duplicate upload to this application (see
        # DocumentRepository.get_by_application_and_hash's docstring): a new
        # Document row would get its own document_id, which the pipeline's
        # replay-safety (keyed on document_id, not content) does not
        # recognize as the same file — it would silently double this
        # application's evidence pool rather than no-op like every other
        # ADR-008 replay path in this system does.
        duplicate = self._repo.get_by_application_and_hash(application_id, content_hash)
        if duplicate is not None:
            raise ConflictError(
                f"This exact file was already uploaded to this application as "
                f"document {duplicate.id} ({duplicate.original_filename!r}, "
                f"{duplicate.ingestion_status}).",
                details={
                    "application_id": str(application_id),
                    "existing_document_id": str(duplicate.id),
                    "content_hash": content_hash,
                },
            )

        # Delegate to StorageProvider — the implementation is fully replaceable.
        storage_ref = self._storage.store(content, content_hash)

        # Create aggregate with PENDING status. Both DOCUMENT_UPLOADED and
        # DOCUMENT_STORED audit events are queued in _pending_events.
        document = Document.create(
            tenant_id=user.tenant_id,
            application_id=application_id,
            uploaded_by=user.user_id,
            original_filename=original_filename,
            mime_type=mime_type,
            size_bytes=len(content),
            content_hash=content_hash,
            storage_reference=storage_ref.reference,
            party_id=party_id,
        )

        # Persist and write audit events atomically in the same session.
        self._repo.save(document, actor=user)

        # Publish the typed Platform Kernel DomainEvent. This is the authoritative
        # signal for the Intelligence Orchestrator to begin the processing pipeline.
        self._event_bus.publish(
            DocumentIngested(
                tenant_id=user.tenant_id,
                document_id=DocumentId(document.id),
                application_id=ApplicationId(application_id),
                storage_reference=storage_ref.reference,
                content_hash=content_hash,
                document_name=original_filename,
            )
        )

        return document

    def get_document(
        self,
        user: AuthenticatedUser,
        *,
        document_id: UUID,
    ) -> Document:
        """
        Retrieve a document by id.

        Raises:
            AuthorizationError: If the caller lacks READ_DOCUMENT permission.
            NotFoundError:      If no document with the given id exists.
        """
        require_permission(user, Permission.READ_DOCUMENT)
        doc = self._repo.get_by_id(document_id)
        if doc is None:
            raise NotFoundError("Document", document_id)
        return doc

    def list_documents(
        self,
        user: AuthenticatedUser,
        *,
        application_id: UUID,
    ) -> list[Document]:
        """
        List all documents associated with an application.

        Raises:
            AuthorizationError: If the caller lacks READ_DOCUMENT permission.
        """
        require_permission(user, Permission.READ_DOCUMENT)
        return self._repo.get_for_application(application_id)

    def retry_ingestion(
        self,
        user: AuthenticatedUser,
        *,
        document_id: UUID,
    ) -> Document:
        """
        Reset a FAILED document back to PENDING so its ingestion pipeline
        (OCR -> Extraction -> Evidence) can be re-triggered.

        Reuses the already-stored file bytes (``storage_reference`` is
        immutable per ADR-006) — no re-upload is ever required. The caller
        is responsible for re-triggering the DOCUMENT_INGESTION workflow
        (see ``DocumentIngestionTrigger.trigger``) after this returns.

        Raises:
            AuthorizationError: If the caller lacks UPLOAD_DOCUMENT permission.
            NotFoundError:      If no document with the given id exists.
            ConflictError:      If the document is not FAILED (retry is only
                                 valid for a terminally failed document —
                                 see ``Document.reset_for_retry``).
        """
        require_permission(user, Permission.UPLOAD_DOCUMENT)
        document = self._repo.get_by_id(document_id)
        if document is None:
            raise NotFoundError("Document", document_id)
        document.reset_for_retry()
        self._repo.save(document, actor=user)
        return document

    @staticmethod
    def compute_content_hash(content: bytes) -> str:
        """
        Compute the SHA-256 content hash for ``content``.

        Provided as a utility for callers that need the hash before calling
        ``ingest_document`` (e.g. for duplicate detection).
        """
        return hashlib.sha256(content).hexdigest()

    # ------------------------------------------------------------------
    # Pipeline lifecycle transitions (system-driven, invoked by workers)
    #
    # DocumentService is the SOLE owner of Document status mutation (ADR-006).
    # The Intelligence Orchestrator and pipeline workers never write to the
    # Document record directly — they call these methods. They run as the
    # platform (SYSTEM actor): no human user, no RBAC check.
    # ------------------------------------------------------------------

    def get_for_pipeline(self, *, document_id: UUID) -> Document:
        """
        Load a document for pipeline processing (system context, no RBAC check).

        Raises:
            NotFoundError: If no document with the given id exists.
        """
        doc = self._repo.get_by_id(document_id)
        if doc is None:
            raise NotFoundError("Document", document_id)
        return doc

    def start_processing(self, *, document_id: UUID) -> Document:
        """
        Transition a document to IN_PROGRESS when pipeline processing begins.

        Idempotent: a document already IN_PROGRESS is returned unchanged (no
        duplicate transition, no duplicate audit event) so that a retried or
        replayed pipeline job is safe (ADR-008).

        Raises:
            NotFoundError: If the document does not exist.
            ConflictError: If the document is in a terminal state (COMPLETED/FAILED).
        """
        from mil.document.models import IngestionStatus

        document = self.get_for_pipeline(document_id=document_id)
        if document.ingestion_status == IngestionStatus.IN_PROGRESS:
            return document
        document.mark_processing()
        self._repo.save(document, actor=None)
        return document

    def complete_processing(
        self, *, document_id: UUID, page_count: int, evidence_item_count: int
    ) -> Document:
        """
        Transition a document to COMPLETED when the full pipeline finishes.

        Driven by the Extraction stage on success. Idempotent: a document
        already COMPLETED is returned unchanged (its existing page_count /
        evidence_item_count / ingestion_completed_at are not overwritten).

        Args:
            document_id:         The document to complete.
            page_count:          Page count from the persisted OCR result.
            evidence_item_count: Number of EvidenceItem rows this document
                                 produced.

        Raises:
            NotFoundError: If the document does not exist.
            ConflictError: If the document is not IN_PROGRESS.
        """
        from mil.document.models import IngestionStatus

        document = self.get_for_pipeline(document_id=document_id)
        if document.ingestion_status == IngestionStatus.COMPLETED:
            return document
        document.mark_completed(page_count=page_count, evidence_item_count=evidence_item_count)
        self._repo.save(document, actor=None)
        return document

    def fail_processing(self, *, document_id: UUID, reason: str) -> Document:
        """
        Transition a document to FAILED on a permanent pipeline failure.

        Idempotent: a document already FAILED is returned unchanged.

        Raises:
            NotFoundError: If the document does not exist.
            ConflictError: If the document is COMPLETED (a completed document
                cannot fail).
        """
        from mil.document.models import IngestionStatus

        document = self.get_for_pipeline(document_id=document_id)
        if document.ingestion_status == IngestionStatus.FAILED:
            return document
        document.mark_failed(reason)
        self._repo.save(document, actor=None)
        return document
