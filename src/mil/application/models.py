"""
ORM models and domain aggregate for the Application & Party bounded context.

MortgageApplication is the Aggregate Root. All mutations to an application's
parties, lifecycle status, and metadata go through aggregate methods on this
class. External code must never modify Party instances directly.

Domain invariants enforced by the aggregate:
- An application must have at least one APPLICANT party before it can be submitted.
- Parties cannot be added to or removed from a WITHDRAWN application.
- Lifecycle state transitions follow the approved MIL state machine (see
  ApplicationStatus and _VALID_TRANSITIONS below).
- Every mutation that changes the aggregate state appends a domain event to
  ``_pending_events``. The repository drains these after flush to write
  the corresponding audit records.

Schema: ``core`` PostgreSQL schema.

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library. No bounded context may import from another bounded context.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, reconstructor, relationship

from mil.kernel.db import Base
from mil.kernel.errors import (
    ConflictError,
    InvalidStateTransitionError,
    NotFoundError,
    ValidationError,
)

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class PartyType(enum.StrEnum):
    """
    The role a party plays within a mortgage application.

    Stored as a VARCHAR string in the database (``core.parties.party_type``)
    rather than a native PostgreSQL ENUM to allow adding values without a
    DDL migration.

    Values match the approved data model enumeration in ``data-model.md``.
    """

    APPLICANT = "APPLICANT"
    CO_APPLICANT = "CO_APPLICANT"
    GUARANTOR = "GUARANTOR"
    CORPORATE_ENTITY = "CORPORATE_ENTITY"


class ApplicationStatus(enum.StrEnum):
    """
    Lifecycle states for a mortgage application within MIL.

    MIL tracks an application's progression through the intelligence review
    workflow. This is NOT a lending decision state — MIL never approves or
    rejects loans (Engineering Constitution, Principle I).

    State machine (allowed transitions in _VALID_TRANSITIONS):

        DRAFT → SUBMITTED → IN_REVIEW → REVIEW_COMPLETE
          ↓         ↓           ↓
        WITHDRAWN ←────────────────────── (from any non-terminal state)

    REVIEW_COMPLETE and WITHDRAWN are terminal states.
    """

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    IN_REVIEW = "IN_REVIEW"
    REVIEW_COMPLETE = "REVIEW_COMPLETE"
    WITHDRAWN = "WITHDRAWN"


# Allowed status transitions. A missing key means the state is terminal.
_VALID_TRANSITIONS: dict[str, set[str]] = {
    ApplicationStatus.DRAFT: {ApplicationStatus.SUBMITTED, ApplicationStatus.WITHDRAWN},
    ApplicationStatus.SUBMITTED: {ApplicationStatus.IN_REVIEW, ApplicationStatus.WITHDRAWN},
    ApplicationStatus.IN_REVIEW: {ApplicationStatus.REVIEW_COMPLETE, ApplicationStatus.WITHDRAWN},
}

_TERMINAL_STATES: frozenset[str] = frozenset(
    {ApplicationStatus.REVIEW_COMPLETE, ApplicationStatus.WITHDRAWN}
)


# ---------------------------------------------------------------------------
# Party entity (owned by MortgageApplication aggregate)
# ---------------------------------------------------------------------------


class Party(Base):
    """
    A person or legal entity associated with a mortgage application.

    Party represents a role that a person or organisation plays in the
    lending transaction: they are the one borrowing (APPLICANT), jointly
    borrowing (CO_APPLICANT), providing security (GUARANTOR), or participating
    as a legal entity (CORPORATE_ENTITY).

    Parties are exclusively created, modified, and removed through the
    ``MortgageApplication`` aggregate root. External code must use the
    aggregate methods; it must not instantiate or mutate Party directly.

    ``display_name`` is a non-PII reference label (e.g. "Primary Borrower").
    Full personal details live in the LOS and are never stored in MIL.

    ``external_identifier_hash``/``identifier_type`` (spec 005-enterprise-
    platform §5, Wave 3 — Borrower Identity Resolution, additive): a SHA-256
    hash of a real external identifier the LOS supplied at intake (customer
    ID, SSN, Aadhaar, PAN, passport number, etc.) plus a free-string label
    naming which kind it is. Never the raw identifier — the same "hash, never
    plaintext" discipline already applied to ``identity.User.email_hash``.
    Both nullable: most parties are created without one, and deterministic
    identity matching (``mil.borrower_identity``) simply has less signal for
    those, never a fabricated value.
    """

    __tablename__ = "parties"
    __table_args__ = {"schema": "core"}

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("core.applications.id"), nullable=False)
    party_type: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    external_identifier_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    identifier_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    application: Mapped[MortgageApplication] = relationship(
        "MortgageApplication", back_populates="parties"
    )

    @property
    def party_type_enum(self) -> PartyType:
        """Return the party type as a typed enum value."""
        return PartyType(self.party_type)

    def __repr__(self) -> str:
        return f"<Party id={self.id} type={self.party_type} app={self.application_id}>"


# ---------------------------------------------------------------------------
# MortgageApplication — Aggregate Root
# ---------------------------------------------------------------------------


class MortgageApplication(Base):
    """
    A mortgage application managed by the MIL intelligence layer.

    This is the Aggregate Root for the Application & Party bounded context.
    It owns the complete application lifecycle, all associated parties, and
    the invariants that govern when and how the application can change state.

    ``MortgageApplication`` exists in MIL to provide the organisational context
    for documents, evidence, and findings. MIL never approves or rejects
    applications — that authority belongs to the underwriter and the LOS.

    ``los_reference`` is the application's identifier in the upstream Loan
    Origination System. It is nullable because MIL can receive a document
    before the LOS application has been formally registered.

    ``loan_number`` is the lender's own loan identifier — distinct from
    ``los_reference`` — and one of the three mandatory, equally-weighted
    identifiers underwriters use to locate an application (alongside borrower
    name and LOS reference; spec 002). Nullable for the same reason as
    ``los_reference``: it may not yet be assigned when the MIL record is created.

    ``created_by`` refers to the authenticated user who initiated the MIL
    application record. In automated integrations this may be a service account.
    """

    __tablename__ = "applications"
    __table_args__ = {"schema": "core"}

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    los_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    loan_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=ApplicationStatus.DRAFT)
    active_policy_pack_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(nullable=False)

    parties: Mapped[list[Party]] = relationship(
        "Party",
        back_populates="application",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        # Non-mapped: accumulates domain events until the repository flushes them.
        self._pending_events: list[dict[str, object]] = []

    @reconstructor
    def _init_on_load(self) -> None:
        # Called by SQLAlchemy when loading an existing record from the DB.
        # __init__ is not called on load, so we must initialise the event queue here.
        self._pending_events = []

    # ------------------------------------------------------------------
    # Factory method
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        created_by: UUID,
        los_reference: str | None = None,
        loan_number: str | None = None,
    ) -> MortgageApplication:
        """
        Create a new mortgage application in DRAFT state.

        This is the only way to obtain a new ``MortgageApplication`` instance.
        Using the factory method rather than the constructor ensures that the
        APPLICATION_CREATED domain event is always recorded.

        Args:
            tenant_id: The institution the application belongs to.
            created_by: The authenticated user (or service account) creating
                the application record in MIL.
            los_reference: The application's identifier in the upstream LOS,
                if already known.
            loan_number: The lender's own loan identifier, if already known.
        """
        now = datetime.now(UTC)
        app = cls(
            id=uuid4(),
            tenant_id=tenant_id,
            created_by=created_by,
            status=ApplicationStatus.DRAFT,
            los_reference=los_reference,
            loan_number=loan_number,
            created_at=now,
            updated_at=now,
        )
        app._pending_events.append(
            {
                "event_type": "APPLICATION_CREATED",
                "entity_type": "APPLICATION",
                "entity_id": app.id,
                "data": {
                    "status": ApplicationStatus.DRAFT,
                    "los_reference": los_reference,
                    "loan_number": loan_number,
                },
            }
        )
        return app

    # ------------------------------------------------------------------
    # Party management (aggregate invariants)
    # ------------------------------------------------------------------

    def add_party(
        self,
        party_type: PartyType,
        display_name: str,
        *,
        external_identifier_hash: str | None = None,
        identifier_type: str | None = None,
    ) -> Party:
        """
        Add a party to this application.

        A party represents a person or organisation's role in the mortgage
        transaction. The mortgage professional adds parties before submitting
        the application for intelligence review.

        Args:
            party_type: The role the party plays (APPLICANT, CO_APPLICANT, etc.).
            display_name: A non-PII label identifying the party (e.g.
                "Primary Borrower", "Joint Applicant").
            external_identifier_hash: Optional SHA-256 hash of a real external
                identifier (spec 005 §5, Wave 3) — the caller computes the
                hash; this aggregate never sees or stores the raw value.
            identifier_type: Optional free-string label for the identifier
                kind (e.g. ``"CUSTOMER_ID"``, ``"SSN_HASH"``).

        Raises:
            ConflictError: If the application is in WITHDRAWN state.
            ValidationError: If ``display_name`` is empty.
        """
        if self.status == ApplicationStatus.WITHDRAWN:
            raise ConflictError(f"Cannot add a party to a WITHDRAWN application (id={self.id})")
        if not display_name or not display_name.strip():
            raise ValidationError("Party display_name must not be empty", field="display_name")

        party = Party(
            id=uuid4(),
            application_id=self.id,
            party_type=party_type.value,
            display_name=display_name.strip(),
            external_identifier_hash=external_identifier_hash,
            identifier_type=identifier_type,
            created_at=datetime.now(UTC),
        )
        self.parties.append(party)
        self._touch()
        self._pending_events.append(
            {
                "event_type": "PARTY_ADDED",
                "entity_type": "PARTY",
                "entity_id": party.id,
                "data": {
                    "party_type": party_type.value,
                    "display_name": party.display_name,
                    "application_id": str(self.id),
                },
            }
        )
        return party

    def remove_party(self, party_id: UUID) -> Party:
        """
        Remove a party from this application.

        Args:
            party_id: The identifier of the party to remove.

        Raises:
            ConflictError: If the application is in a terminal state.
            NotFoundError: If no party with the given ID belongs to this application.
        """
        if self.status in _TERMINAL_STATES:
            raise ConflictError(
                f"Cannot remove a party from a {self.status} application (id={self.id})"
            )

        party = next((p for p in self.parties if p.id == party_id), None)
        if party is None:
            raise NotFoundError("Party", party_id, {"application_id": str(self.id)})

        self.parties.remove(party)
        self._touch()
        self._pending_events.append(
            {
                "event_type": "PARTY_REMOVED",
                "entity_type": "PARTY",
                "entity_id": party_id,
                "data": {
                    "party_type": party.party_type,
                    "application_id": str(self.id),
                },
            }
        )
        return party

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def submit(self) -> None:
        """
        Advance the application from DRAFT to SUBMITTED for intelligence review.

        Business rule: at least one party of type APPLICANT must be registered
        before the application can be submitted. Without an applicant, evidence
        cannot be attributed to a borrower.

        Raises:
            ConflictError: If there are no APPLICANT parties.
            InvalidStateTransitionError: If the current status does not allow
                a transition to SUBMITTED.
        """
        applicants = [p for p in self.parties if p.party_type == PartyType.APPLICANT]
        if not applicants:
            raise ConflictError(
                "Application cannot be submitted: at least one APPLICANT party is required"
            )
        self._transition_to(ApplicationStatus.SUBMITTED)

    def start_review(self) -> None:
        """
        Advance from SUBMITTED to IN_REVIEW once evidence extraction begins.

        Raises:
            InvalidStateTransitionError: If not currently SUBMITTED.
        """
        self._transition_to(ApplicationStatus.IN_REVIEW)

    def complete_review(self) -> None:
        """
        Mark review as complete (terminal state: REVIEW_COMPLETE).

        Raises:
            InvalidStateTransitionError: If not currently IN_REVIEW.
        """
        self._transition_to(ApplicationStatus.REVIEW_COMPLETE)

    def withdraw(self) -> None:
        """
        Withdraw the application (terminal state: WITHDRAWN).

        Raises:
            InvalidStateTransitionError: If already in a terminal state.
        """
        self._transition_to(ApplicationStatus.WITHDRAWN)

    # ------------------------------------------------------------------
    # Pending event protocol (consumed by ApplicationRepository)
    # ------------------------------------------------------------------

    def collect_pending_events(self) -> list[dict[str, object]]:
        """
        Return and clear the queue of pending domain events.

        The repository calls this after flushing the session. The returned
        events are written as audit records in the same database transaction.
        Callers must not call this method; it is part of the repository protocol.
        """
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _transition_to(self, new_status: ApplicationStatus) -> None:
        allowed = _VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise InvalidStateTransitionError(
                entity_type="MortgageApplication",
                entity_id=self.id,
                from_state=self.status,
                to_state=new_status,
            )
        old_status = self.status
        self.status = new_status
        self._touch()
        self._pending_events.append(
            {
                "event_type": "APPLICATION_STATE_CHANGED",
                "entity_type": "APPLICATION",
                "entity_id": self.id,
                "data": {
                    "from_status": old_status,
                    "to_status": new_status,
                },
            }
        )

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)

    @property
    def status_enum(self) -> ApplicationStatus:
        """Return the current status as a typed enum value."""
        return ApplicationStatus(self.status)

    @property
    def applicant_parties(self) -> list[Party]:
        """Return only the APPLICANT-type parties."""
        return [p for p in self.parties if p.party_type == PartyType.APPLICANT]

    def __repr__(self) -> str:
        return f"<MortgageApplication id={self.id} status={self.status} tenant={self.tenant_id}>"


# T034 complete. T035 will add ApplicationRepository and AuditWriter.
# T038 will add Document model (document processing bounded context).
