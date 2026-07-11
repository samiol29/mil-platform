"""
Repository for the Document Processing bounded context.

``DocumentRepository`` is the only persistence gateway for ``Document`` records.
All audit events emitted by the document aggregate are drained here and written
to the audit log via ``AuditWriter`` in the same database transaction.

ADR-005 note: Document's internal state events (DOCUMENT_UPLOADED,
DOCUMENT_STORED) use the same dict-based pending event pattern as
``MortgageApplication``. This is the intentional transitional design documented
in ADR-005. Migration to typed ``DomainEvent`` objects is deferred to US2.
The platform-level coordination event (``DocumentIngested``) is published on the
``EventBus`` by ``DocumentService`` using the typed ``DomainEvent`` hierarchy
from ``mil.kernel.events`` — that IS the full adoption path for external events.

Dependency rule: imports only from ``mil.document.models``, ``mil.kernel``,
and the Python standard library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from mil.document.models import Document

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session

    from mil.audit.writer import AuditWriter
    from mil.kernel.security import AuthenticatedUser


class DocumentRepository:
    """
    Persistence gateway for the Document aggregate.

    Responsibilities:
    - Persist new Document records (``save``).
    - Drain pending domain events to the audit log after each flush.
    - Retrieve documents by id or by application.

    There is no ``PartyRepository`` — parties are loaded through
    ``ApplicationRepository``. Similarly, there is no method here that
    modifies the ``MortgageApplication`` aggregate — cross-context state
    changes use domain events on the ``EventBus``.
    """

    def __init__(self, session: Session, audit_writer: AuditWriter) -> None:
        self._session = session
        self._audit = audit_writer

    def save(self, document: Document, *, actor: AuthenticatedUser | None) -> None:
        """
        Persist ``document`` and drain its pending events to the audit log.

        The drain happens in three steps:
          1. Collect pending events BEFORE flush (they reference pre-flush state).
          2. Add document to the session and flush.
          3. Write each event as an AuditEvent in the SAME session.

        ``actor`` is the authenticated user responsible for the change, or
        ``None`` for system-driven pipeline transitions (OCR worker, etc.). When
        ``None``, the audit event records a SYSTEM actor (``actor_id`` is null),
        per the ``AuditWriter`` contract.

        Atomicity: if ``session.flush()`` raises, pending events are not written.
        If ``audit.record()`` raises, the transaction rolls back with the domain flush.
        """
        pending = document.collect_pending_events()
        self._session.add(document)
        self._session.flush()
        actor_id = actor.user_id if actor is not None else None
        for event in pending:
            self._audit.record(
                event_type=str(event["event_type"]),
                entity_type=str(event["entity_type"]),
                entity_id=event["entity_id"],  # type: ignore[arg-type]
                tenant_id=document.tenant_id,
                application_id=document.application_id,
                actor_id=actor_id,
                event_data=event.get("data") or {},  # type: ignore[arg-type]
            )

    def get_by_id(self, document_id: UUID) -> Document | None:
        """Return the Document with the given id, or ``None`` if not found."""
        return self._session.get(Document, document_id)

    def get_for_application(self, application_id: UUID) -> list[Document]:
        """
        Return all documents associated with the given application.

        Results are ordered by upload time, most recent first.
        """
        stmt = (
            select(Document)
            .where(Document.application_id == application_id)
            .order_by(Document.uploaded_at.desc())
        )
        return list(self._session.scalars(stmt))

    def exists(self, document_id: UUID) -> bool:
        """Return ``True`` if a Document with the given id exists."""
        return self.get_by_id(document_id) is not None

    def count_for_tenant(self, tenant_id: UUID) -> int:
        """
        Return the total Document count for a tenant (spec 005-enterprise-
        platform §11, Wave 3 — Business Analytics' document-volume signal).
        """
        stmt = select(func.count(Document.id)).where(Document.tenant_id == tenant_id)
        return int(self._session.scalars(stmt).one())

    def search_for_tenant(
        self, tenant_id: UUID, search: str, *, limit: int = 20
    ) -> list[Document]:
        """
        Case-insensitive substring match against ``original_filename``,
        scoped to the tenant (spec 005-enterprise-platform §7, Universal
        Search Expansion). Plain ``ILIKE``, matching the exact same non-
        full-text-search discipline already established by
        ``ApplicationRepository.get_for_tenant``'s own ``search`` param — no
        new search infrastructure introduced.

        Filename only: confirmed by direct inspection that ``Document`` has
        no ``document_type``/category column at all (the frontend's own
        "detected type" is a client-side-only heuristic over the filename,
        never persisted) — this method does not invent a second field to
        search against.
        """
        pattern = f"%{search}%"
        stmt = (
            select(Document)
            .where(Document.tenant_id == tenant_id, Document.original_filename.ilike(pattern))
            .order_by(Document.uploaded_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt))

    def get_by_application_and_hash(
        self, application_id: UUID, content_hash: str
    ) -> Document | None:
        """
        Return the Document already uploaded to this application with this
        exact content hash, or ``None`` if this is a new file.

        Used by ``DocumentService.ingest_document`` to reject a byte-for-byte
        duplicate upload (ADR-008-style content identity, applied to uploads
        rather than replays): without this check, re-uploading the same file
        to the same application creates a second ``Document`` row with its
        own ``document_id``, which the pipeline's replay-safety (keyed on
        ``document_id``) does not recognize as a duplicate — it runs OCR and
        Extraction again and doubles that application's evidence pool.
        """
        stmt = select(Document).where(
            Document.application_id == application_id,
            Document.content_hash == content_hash,
        )
        return self._session.scalars(stmt).first()
