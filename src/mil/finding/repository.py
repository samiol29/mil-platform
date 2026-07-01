"""
Persistence gateway for Findings (Finding Management bounded context).

``FindingRepository`` is append-only: it writes immutable ``Finding`` rows and
never updates or deletes them. It does not commit — the caller (the Finding
worker's per-job Unit of Work) owns the transaction.

Idempotency (ADR-008): ``exists_for_application_and_version`` lets the Finding
worker detect a replay (a Finding already exists for this application under
this inference model version) and treat it as a no-op rather than generating a
duplicate; the unique constraint on ``(application_id, model_version)`` is the
backing authority.

Dependency rule: imports only from ``mil.finding.models``, ``mil.kernel``, and
the Python standard library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from mil.finding.models import Finding

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session


class FindingRepository:
    """Append-only gateway for ``Finding`` rows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, finding: Finding) -> None:
        """
        Persist an immutable Finding.

        Adds the finding and flushes so a uniqueness violation (duplicate
        application + model version) surfaces within the caller's transaction.
        """
        self._session.add(finding)
        self._session.flush()

    def get_for_application(self, application_id: UUID) -> list[Finding]:
        """Return all findings for an application, most recent first."""
        stmt = (
            select(Finding)
            .where(Finding.application_id == application_id)
            .order_by(Finding.created_at.desc())
        )
        return list(self._session.scalars(stmt))

    def exists_for_application_and_version(self, application_id: UUID, model_version: str) -> bool:
        """
        Return ``True`` if a Finding already exists for an application under a
        given inference model version.

        This is the job-level idempotency check (ADR-008): a non-``False``
        result means this application has already been evaluated
        deterministically under this model version, within the same
        all-or-nothing per-job transaction.
        """
        stmt = select(Finding.id).where(
            Finding.application_id == application_id,
            Finding.model_version == model_version,
        )
        return self._session.scalars(stmt).first() is not None
