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

from sqlalchemy import select

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
