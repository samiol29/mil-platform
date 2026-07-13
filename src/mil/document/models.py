"""
ORM model and domain entity for the Document Processing bounded context.

Document is the canonical record of a source file submitted as part of a
mortgage application. It is the platform's source of truth for:

    "Exactly which file was uploaded?"
    "Can we prove this is the same file that produced this evidence?"

Immutability guarantees:
- ``content_hash`` is computed exactly once during ingestion and never changes.
- ``storage_reference`` is set once when the file is written to durable storage
  and never changes.
- ``original_filename`` is metadata only. Business logic must never depend on
  filenames. Document identity is determined by id, content_hash, and
  storage_reference.

``ingestion_status`` tracks the document's position in the intelligence
pipeline. Documents start at PENDING (uploaded, awaiting OCR/extraction).
The Intelligence Orchestrator (US2) drives transitions to IN_PROGRESS and
COMPLETED. FAILED records a permanent pipeline error.

Future OCR, Evidence, Findings, and Intelligence workflows must reference
documents by Document.id — not by filename or storage path.

Schema: ``core`` PostgreSQL schema.

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, reconstructor

from mil.kernel.db import Base
from mil.kernel.errors import ConflictError, ValidationError

# ---------------------------------------------------------------------------
# Enumeration
# ---------------------------------------------------------------------------

_CONTENT_HASH_LENGTH = 64  # SHA-256 hex digest is exactly 64 characters


class IngestionStatus(enum.StrEnum):
    """
    Lifecycle state of a document within the intelligence processing pipeline.

    Documents are uploaded and stored synchronously (Sprint 3C). The OCR and
    evidence extraction pipeline (US2) drives transitions from PENDING through
    IN_PROGRESS to COMPLETED or FAILED.

    PENDING and FAILED are the only states relevant to Sprint 3C.
    """

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Document ORM entity
# ---------------------------------------------------------------------------


class Document(Base):
    """
    A source document submitted as part of a mortgage application in MIL.

    Documents are immutable assets: once the file is stored and the record
    persisted, the content_hash and storage_reference never change.
    The Intelligence Pipeline (US2) reads documents by id — never by filename
    or path. The original_filename is preserved as metadata for display only.

    ``ingestion_status`` begins at PENDING and advances through the intelligence
    processing pipeline. In Sprint 3C (document custody only), documents remain
    at PENDING. US2 introduces the IN_PROGRESS and COMPLETED transitions.

    ``party_id`` optionally associates the document with a specific party within
    the application (e.g. "This income statement belongs to the Primary Borrower").
    Documents without a party association are application-level uploads.
    """

    __tablename__ = "documents"
    __table_args__ = {"schema": "core"}

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("core.applications.id"), nullable=False)
    party_id: Mapped[UUID | None] = mapped_column(ForeignKey("core.parties.id"), nullable=True)
    uploaded_by: Mapped[UUID] = mapped_column(nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # SHA-256 hex digest — set once at ingestion, immutable thereafter.
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    # Content-addressed storage reference — set once at ingestion, immutable.
    storage_reference: Mapped[str] = mapped_column(Text, nullable=False)
    ingestion_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=IngestionStatus.PENDING
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Pipeline outcome projections, populated once the DOCUMENT_INGESTION
    # workflow reaches a terminal state. All four remain unset (None / 0)
    # while the document is PENDING or IN_PROGRESS.
    page_count: Mapped[int | None] = mapped_column(nullable=True)
    evidence_item_count: Mapped[int] = mapped_column(nullable=False, default=0)
    ingestion_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ingestion_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Number of times ingestion has been retried after a FAILED terminal
    # state. Zero until the first retry. Drives the idempotency key for each
    # re-triggered DOCUMENT_INGESTION workflow (see reset_for_retry()) and is
    # surfaced verbatim in processing feedback ("Attempt 2 of 3").
    retry_count: Mapped[int] = mapped_column(nullable=False, default=0)

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._pending_events: list[dict[str, object]] = []

    @reconstructor
    def _init_on_load(self) -> None:
        # SQLAlchemy bypasses __init__ when loading from DB; re-initialise here.
        self._pending_events = []

    # ------------------------------------------------------------------
    # Factory method
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        application_id: UUID,
        uploaded_by: UUID,
        original_filename: str,
        mime_type: str,
        size_bytes: int,
        content_hash: str,
        storage_reference: str,
        party_id: UUID | None = None,
    ) -> Document:
        """
        Register an uploaded document that has been written to durable storage.

        The ``content_hash`` and ``storage_reference`` are immutable for the
        lifetime of this record. The ``ingestion_status`` starts at PENDING —
        the Intelligence Pipeline (US2) advances it through IN_PROGRESS to
        COMPLETED or FAILED.

        Both DOCUMENT_UPLOADED and DOCUMENT_STORED audit events are queued in
        ``_pending_events``. The repository drains them after flush.

        Args:
            tenant_id:          Institution this document belongs to.
            application_id:     Application the document is associated with.
            uploaded_by:        Authenticated user who initiated the upload.
            original_filename:  Display metadata only — never used for routing.
            mime_type:          IANA media type of the file (e.g. "application/pdf").
            size_bytes:         File size in bytes.
            content_hash:       SHA-256 hex digest (64 characters), computed by
                                the caller exactly once before this call.
            storage_reference:  Content-addressed storage reference returned by
                                ``StorageProvider.store()``.
            party_id:           Optional party within the application this
                                document pertains to.
        """
        if not original_filename or not original_filename.strip():
            raise ValidationError("original_filename must not be empty", field="original_filename")
        if not mime_type or not mime_type.strip():
            raise ValidationError("mime_type must not be empty", field="mime_type")
        if size_bytes < 0:
            raise ValidationError("size_bytes cannot be negative", field="size_bytes")
        if not content_hash or len(content_hash) != _CONTENT_HASH_LENGTH:
            raise ValidationError(
                f"content_hash must be a {_CONTENT_HASH_LENGTH}-character SHA-256 hex digest",
                field="content_hash",
            )
        if not storage_reference or not storage_reference.strip():
            raise ValidationError("storage_reference must not be empty", field="storage_reference")

        now = datetime.now(UTC)
        doc = cls(
            id=uuid4(),
            tenant_id=tenant_id,
            application_id=application_id,
            party_id=party_id,
            uploaded_by=uploaded_by,
            original_filename=original_filename.strip(),
            mime_type=mime_type.strip(),
            size_bytes=size_bytes,
            content_hash=content_hash,
            storage_reference=storage_reference.strip(),
            ingestion_status=IngestionStatus.PENDING,
            uploaded_at=now,
            page_count=None,
            evidence_item_count=0,
            ingestion_completed_at=None,
            ingestion_error=None,
            retry_count=0,
        )

        # DOCUMENT_UPLOADED: the business action — a user submitted a file.
        doc._pending_events.append(
            {
                "event_type": "DOCUMENT_UPLOADED",
                "entity_type": "DOCUMENT",
                "entity_id": doc.id,
                "data": {
                    "application_id": str(application_id),
                    "original_filename": original_filename.strip(),
                    "mime_type": mime_type.strip(),
                    "size_bytes": size_bytes,
                    "content_hash": content_hash,
                    "party_id": str(party_id) if party_id else None,
                },
            }
        )

        # DOCUMENT_STORED: technical confirmation that bytes are durable.
        doc._pending_events.append(
            {
                "event_type": "DOCUMENT_STORED",
                "entity_type": "DOCUMENT",
                "entity_id": doc.id,
                "data": {
                    "application_id": str(application_id),
                    "storage_reference": storage_reference.strip(),
                    "content_hash": content_hash,
                    "size_bytes": size_bytes,
                },
            }
        )

        return doc

    # ------------------------------------------------------------------
    # Status transitions (used by Intelligence Pipeline — US2)
    # ------------------------------------------------------------------

    def mark_processing(self) -> None:
        """
        Advance from PENDING to IN_PROGRESS when the pipeline begins.

        Enqueues a DOCUMENT_INGESTION_STARTED audit event so the lifecycle is
        fully reconstructable (Principle VIII).
        """
        if self.ingestion_status != IngestionStatus.PENDING:
            raise ConflictError(
                f"Cannot start processing a {self.ingestion_status} document (id={self.id})"
            )
        self.ingestion_status = IngestionStatus.IN_PROGRESS
        self._pending_events.append(
            {
                "event_type": "DOCUMENT_INGESTION_STARTED",
                "entity_type": "DOCUMENT",
                "entity_id": self.id,
                "data": {
                    "application_id": str(self.application_id),
                    "content_hash": self.content_hash,
                },
            }
        )

    def mark_completed(self, *, page_count: int, evidence_item_count: int) -> None:
        """
        Advance from IN_PROGRESS to COMPLETED when the pipeline finishes.

        Populates the pipeline outcome projections (``page_count``,
        ``evidence_item_count``, ``ingestion_completed_at``) so the API can
        report real values instead of placeholder defaults. Enqueues a
        DOCUMENT_INGESTION_COMPLETED audit event.
        """
        if self.ingestion_status != IngestionStatus.IN_PROGRESS:
            raise ConflictError(
                f"Cannot complete a {self.ingestion_status} document (id={self.id})"
            )
        self.ingestion_status = IngestionStatus.COMPLETED
        self.page_count = page_count
        self.evidence_item_count = evidence_item_count
        self.ingestion_completed_at = datetime.now(UTC)
        self._pending_events.append(
            {
                "event_type": "DOCUMENT_INGESTION_COMPLETED",
                "entity_type": "DOCUMENT",
                "entity_id": self.id,
                "data": {
                    "application_id": str(self.application_id),
                    "content_hash": self.content_hash,
                    "page_count": page_count,
                    "evidence_item_count": evidence_item_count,
                },
            }
        )

    def mark_failed(self, reason: str) -> None:
        """
        Transition to FAILED when the intelligence pipeline encounters an
        unrecoverable error.

        FAILED is a terminal state. The document record (and its immutable
        content in storage) is retained for audit purposes. ``reason`` is
        persisted to ``ingestion_error`` so the API can surface it.
        """
        if self.ingestion_status == IngestionStatus.COMPLETED:
            raise ConflictError(f"Cannot fail a COMPLETED document (id={self.id})")
        self.ingestion_status = IngestionStatus.FAILED
        self.ingestion_error = reason
        self._pending_events.append(
            {
                "event_type": "DOCUMENT_INGESTION_FAILED",
                "entity_type": "DOCUMENT",
                "entity_id": self.id,
                "data": {
                    "application_id": str(self.application_id),
                    "reason": reason,
                    "content_hash": self.content_hash,
                },
            }
        )

    def reset_for_retry(self) -> None:
        """
        Reset a FAILED document back to PENDING so the ingestion pipeline can
        be re-triggered from scratch.

        Only FAILED documents may be retried — a PENDING/IN_PROGRESS document
        already has a workflow in flight, and a COMPLETED document has
        nothing to retry (ADR-006: documents and their storage bytes are
        immutable, so retry never re-uploads, it only re-runs the pipeline).
        Increments ``retry_count`` so the caller can mint a fresh, distinguishing
        idempotency key for the workflow (a repeat key would be a no-op —
        ``IntelligenceOrchestrator.start_workflow`` returns the existing run).
        Clears the prior ``ingestion_error`` since it no longer describes the
        document's current state.
        """
        if self.ingestion_status != IngestionStatus.FAILED:
            raise ConflictError(
                f"Cannot retry a {self.ingestion_status} document (id={self.id}) — "
                "only FAILED documents can be retried"
            )
        self.ingestion_status = IngestionStatus.PENDING
        self.ingestion_error = None
        self.retry_count += 1
        self._pending_events.append(
            {
                "event_type": "DOCUMENT_INGESTION_RETRIED",
                "entity_type": "DOCUMENT",
                "entity_id": self.id,
                "data": {
                    "application_id": str(self.application_id),
                    "content_hash": self.content_hash,
                    "retry_count": self.retry_count,
                },
            }
        )

    # ------------------------------------------------------------------
    # Pending event protocol (consumed by DocumentRepository)
    # ------------------------------------------------------------------

    def collect_pending_events(self) -> list[dict[str, object]]:
        """
        Return and clear the queue of pending domain events.

        Called by DocumentRepository after flushing the session. The returned
        events are written as audit records in the same database transaction.
        Only DocumentRepository may call this method.
        """
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def ingestion_status_enum(self) -> IngestionStatus:
        """Return the current status as a typed enum value."""
        return IngestionStatus(self.ingestion_status)

    @property
    def is_pending(self) -> bool:
        return self.ingestion_status == IngestionStatus.PENDING

    @property
    def is_completed(self) -> bool:
        return self.ingestion_status == IngestionStatus.COMPLETED

    def __repr__(self) -> str:
        return (
            f"<Document id={self.id} status={self.ingestion_status} "
            f"hash={self.content_hash[:8]}...>"
        )
