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

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

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

    def save_if_not_exists(self, finding: Finding) -> bool:
        """
        Persist an immutable Finding, treating a uniqueness violation as
        proof a Finding was already committed for this (application, model
        version) by a prior attempt (ADR-008 §5) rather than an error — the
        authoritative fallback beneath ``exists_for_application_and_version``'s
        read-then-write check, which alone is subject to a race between
        concurrent workers. Isolated with a SAVEPOINT (``session.begin_nested``)
        so a collision here cannot poison the caller's per-job Unit of Work.

        Returns:
            ``True`` if this call newly persisted the Finding, ``False`` if
            one already existed (a replay no-op).
        """
        try:
            with self._session.begin_nested():
                self._session.add(finding)
                self._session.flush()
        except IntegrityError:
            return False
        return True

    def get_for_application(self, application_id: UUID) -> list[Finding]:
        """Return all findings for an application, most recent first."""
        stmt = (
            select(Finding)
            .where(Finding.application_id == application_id)
            .order_by(Finding.created_at.desc())
        )
        return list(self._session.scalars(stmt))

    def get_by_id(self, finding_id: UUID) -> Finding | None:
        """Return the Finding with the given id, or ``None`` if not found."""
        return self._session.get(Finding, finding_id)

    def get_by_application_and_version(
        self, application_id: UUID, model_version: str
    ) -> Finding | None:
        """
        Return the Finding for an application under a given inference model
        version, or ``None``. Used to recover the pre-existing Finding when
        ``save_if_not_exists`` reports a replay collision — the caller (the
        Finding worker) still needs a real ``Finding`` to dispatch the next
        workflow step.
        """
        stmt = select(Finding).where(
            Finding.application_id == application_id,
            Finding.model_version == model_version,
        )
        return self._session.scalars(stmt).one_or_none()

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

    def count_by_lifecycle_state(self, tenant_id: UUID) -> list[tuple[str, int]]:
        """
        Return ``(lifecycle_state, count)`` rows for every Finding in a tenant
        (spec 005-enterprise-platform §11, Wave 3 — Business Analytics' real
        verification/override/escalation-rate signal). One aggregated query.
        """
        stmt = (
            select(Finding.lifecycle_state, func.count(Finding.id))
            .where(Finding.tenant_id == tenant_id)
            .group_by(Finding.lifecycle_state)
        )
        return [(state, int(count)) for state, count in self._session.execute(stmt).all()]
