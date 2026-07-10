"""
Repository for the Application & Party bounded context.

``ApplicationRepository`` is the only persistence mechanism for the
``MortgageApplication`` aggregate root. It loads and saves complete aggregate
instances — it never persists a ``Party`` in isolation because parties are
owned by the aggregate.

Responsibilities:
- Save (INSERT or UPDATE) a ``MortgageApplication`` and its parties.
- Load a ``MortgageApplication`` by ID, with parties eagerly loaded.
- After each save, drain the aggregate's pending domain events and write
  the corresponding audit records via ``AuditWriter``.
- Query applications by tenant for listing.

Audit events emitted (via ``AuditWriter`` in the same transaction):
- ``APPLICATION_CREATED`` — when a new application is first saved.
- ``PARTY_ADDED`` — when ``add_party()`` was called before this save.
- ``PARTY_REMOVED`` — when ``remove_party()`` was called before this save.
- ``APPLICATION_STATE_CHANGED`` — when a lifecycle transition was made.

The repository holds no opinion on whether to commit or rollback. The caller
(typically ``ApplicationService``) controls the session lifecycle.

Dependency rule: imports only from ``mil.kernel``, ``mil.application.models``,
and ``mil.audit``. No other bounded context may be imported.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, cast, or_, select

from mil.application.models import MortgageApplication, Party

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session

    from mil.audit.writer import AuditWriter
    from mil.kernel.security import AuthenticatedUser
    from mil.kernel.types import ApplicationId, TenantId


class ApplicationRepository:
    """
    Persistence gateway for the ``MortgageApplication`` aggregate root.

    Inject this into ``ApplicationService``. Do not use it directly from
    API route handlers.

    Both ``session`` and ``audit_writer`` are injected so that all writes —
    domain data and audit records — land in the same database transaction.
    """

    def __init__(self, session: Session, audit_writer: AuditWriter) -> None:
        self._session = session
        self._audit = audit_writer

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(
        self,
        application: MortgageApplication,
        *,
        actor: AuthenticatedUser,
    ) -> None:
        """
        Persist the aggregate and flush pending domain events as audit records.

        If the application has never been saved (transient), this performs an
        INSERT. If it is already tracked by the session (persistent), any
        mutations are flushed as UPDATEs.

        Pending events are collected from the aggregate, the session is flushed
        (resolving any server-side defaults), and then audit records are written
        within the same session. The caller commits.

        Args:
            application: The aggregate to persist.
            actor: The authenticated principal whose action triggered this save.
        """
        # Collect domain events before flush (the aggregate clears the queue).
        pending = application.collect_pending_events()

        self._session.add(application)
        self._session.flush()

        # Write audit records in the same transaction.
        for evt in pending:
            self._audit.record(
                event_type=str(evt["event_type"]),
                entity_type=str(evt["entity_type"]),
                entity_id=evt["entity_id"],  # type: ignore[arg-type]
                tenant_id=application.tenant_id,
                application_id=application.id,
                actor_id=actor.user_id,
                event_data=evt.get("data", {}),  # type: ignore[arg-type]
            )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_id(self, application_id: ApplicationId | UUID) -> MortgageApplication | None:
        """
        Load a mortgage application by its primary key.

        Returns None if no application with the given ID exists.  The
        ``parties`` relationship is loaded eagerly by issuing a second
        SELECT in the same unit of work (SQLAlchemy lazy-load default on
        first access).

        Args:
            application_id: The UUID of the application to load.
        """
        return self._session.get(MortgageApplication, application_id)

    def get_for_tenant(
        self,
        tenant_id: TenantId | UUID,
        *,
        status: str | None = None,
        search: str | None = None,
    ) -> list[MortgageApplication]:
        """
        Return all applications belonging to a tenant.

        Optionally filter by ``status`` (e.g. ``ApplicationStatus.DRAFT``).
        Results are ordered by ``created_at`` descending (newest first).

        ``search`` performs a case-insensitive substring match against fields
        that already exist on the aggregate — ``los_reference``,
        ``loan_number``, the application's own ``id`` (as text), and any
        registered party's ``display_name`` (via an ``EXISTS`` subquery over
        the ``parties`` relationship, not a join that could duplicate rows).
        This is plain ``ILIKE`` matching, not full-text search — no new
        search infrastructure (indexes, extensions, external index) is
        introduced; if search performance against the ``parties`` subquery
        or these columns becomes a problem at scale, that is a follow-up
        indexing decision, not a change to this method's contract.

        Args:
            tenant_id: The tenant whose applications to return.
            status: Optional status string to filter by.
            search: Optional case-insensitive substring to match against
                LOS reference, loan number, application ID, or borrower
                display name.
        """
        stmt = (
            select(MortgageApplication)
            .where(MortgageApplication.tenant_id == tenant_id)
            .order_by(MortgageApplication.created_at.desc())
        )
        if status is not None:
            stmt = stmt.where(MortgageApplication.status == status)
        if search is not None:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    MortgageApplication.los_reference.ilike(pattern),
                    MortgageApplication.loan_number.ilike(pattern),
                    cast(MortgageApplication.id, String).ilike(pattern),
                    MortgageApplication.parties.any(Party.display_name.ilike(pattern)),
                )
            )
        return list(self._session.scalars(stmt))

    def exists(self, application_id: ApplicationId | UUID) -> bool:
        """
        Return True if an application with the given ID exists.

        Args:
            application_id: The UUID to check.
        """
        return self.get_by_id(application_id) is not None
