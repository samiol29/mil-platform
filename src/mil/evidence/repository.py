"""
Persistence gateway for Evidence items (Evidence Management bounded context).

``EvidenceRepository`` is append-only: it writes immutable ``EvidenceItem``
rows and never updates or deletes them. It does not commit — the caller (the
Extraction worker's per-job Unit of Work) owns the transaction.

Idempotency (ADR-008): ``exists_for_document_and_version`` lets the Extraction
worker detect a replay (evidence already extracted for this document under
this extraction version) and treat it as a no-op rather than re-extracting;
the unique constraint on ``(document_id, extraction_model_version,
evidence_type)`` is the backing authority.

Dependency rule: imports only from ``mil.evidence.models``, ``mil.kernel``,
and the Python standard library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from mil.evidence.models import EvidenceItem

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session


class EvidenceRepository:
    """Append-only gateway for ``EvidenceItem`` rows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, item: EvidenceItem) -> None:
        """
        Persist an immutable evidence item.

        Adds the item and flushes so a uniqueness violation (duplicate
        document + extraction version + evidence type) surfaces within the
        caller's transaction.
        """
        self._session.add(item)
        self._session.flush()

    def save_if_not_exists(self, item: EvidenceItem) -> bool:
        """
        Persist an immutable evidence item, treating a uniqueness violation
        as proof the item was already committed by a prior attempt (ADR-008
        §5) rather than an error.

        ``exists_for_document_and_version`` is a read-then-write check and is
        the caller's *first* line of defense; it is subject to a race between
        two concurrent workers (ADR-008 explicitly anticipates multiple
        replicas). This method is the authoritative fallback: the unique
        constraint ``uq_evidence_items_document_version_type`` is the actual
        source of truth. A single failed item is isolated with a SAVEPOINT
        (``session.begin_nested``) so the rest of the caller's per-job Unit of
        Work — and any other items in the same extraction batch — are
        unaffected by this one collision.

        Returns:
            ``True`` if this call newly persisted the item, ``False`` if an
            equivalent item already existed (a replay no-op for this item).
        """
        try:
            with self._session.begin_nested():
                self._session.add(item)
                self._session.flush()
        except IntegrityError:
            return False
        return True

    def get_for_document(self, document_id: UUID) -> list[EvidenceItem]:
        """Return all evidence items for a document, most recent first."""
        stmt = (
            select(EvidenceItem)
            .where(EvidenceItem.document_id == document_id)
            .order_by(EvidenceItem.created_at.desc())
        )
        return list(self._session.scalars(stmt))

    def get_for_application(self, application_id: UUID) -> list[EvidenceItem]:
        """Return all evidence items for an application, most recent first."""
        stmt = (
            select(EvidenceItem)
            .where(EvidenceItem.application_id == application_id)
            .order_by(EvidenceItem.created_at.desc())
        )
        return list(self._session.scalars(stmt))

    def count_for_tenant(self, tenant_id: UUID) -> int:
        """
        Return the total EvidenceItem count for a tenant (spec 005-
        enterprise-platform §11, Wave 3 — Business Analytics' evidence-
        volume signal).
        """
        stmt = select(func.count(EvidenceItem.id)).where(EvidenceItem.tenant_id == tenant_id)
        return int(self._session.scalars(stmt).one())

    def exists_for_document_and_version(self, document_id: UUID, extraction_version: str) -> bool:
        """
        Return ``True`` if any evidence item already exists for a document
        under a given extraction version.

        This is the job-level idempotency check (ADR-008): a non-``False``
        result means this document has already been extracted deterministically
        under this extraction version, within the same all-or-nothing
        per-job transaction.
        """
        stmt = select(EvidenceItem.id).where(
            EvidenceItem.document_id == document_id,
            EvidenceItem.extraction_model_version == extraction_version,
        )
        return self._session.scalars(stmt).first() is not None
