"""
Application service for the Application & Party bounded context.

``ApplicationService`` is the primary entry point for all use cases in this
bounded context. It orchestrates the ``MortgageApplication`` aggregate and
``ApplicationRepository`` to fulfil client requests without exposing persistence
or domain internals.

Use cases provided:
- Create a new mortgage application.
- Add a party (APPLICANT, CO_APPLICANT, GUARANTOR, CORPORATE_ENTITY).
- Remove a party.
- Submit an application for intelligence review.
- Withdraw an application.
- Retrieve an application by ID.
- List all applications for a tenant.

Audit events are emitted by the repository, not the service. The service
ensures the caller has the required permissions before delegating to the
aggregate and repository.

Party type validation belongs in the service because the caller supplies a
string from the API layer; the domain entity uses the enum. Centralising the
parse-and-validate step here keeps the aggregate clean.

Dependency rule: imports only from ``mil.kernel``, ``mil.application.models``,
and ``mil.application.repository``. No other bounded context is imported.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mil.application.models import MortgageApplication, Party, PartyType
from mil.kernel.errors import NotFoundError, ValidationError
from mil.kernel.security import Permission, require_permission

if TYPE_CHECKING:
    from uuid import UUID

    from mil.application.repository import ApplicationRepository
    from mil.kernel.security import AuthenticatedUser
    from mil.kernel.types import ApplicationId, TenantId


class ApplicationService:
    """
    Application and Party use-case orchestrator.

    The service enforces RBAC permissions before delegating to the aggregate
    and repository. ABAC (tenant-scope) enforcement is intentionally deferred
    to Sprint 3C when the API middleware is added; service-layer callers are
    expected to supply a correctly-scoped ``AuthenticatedUser``.

    Instantiate with an ``ApplicationRepository`` that is already bound to an
    active database session. Session lifecycle (commit/rollback) is managed by
    the caller — typically the API middleware or a test fixture.
    """

    def __init__(self, repository: ApplicationRepository) -> None:
        self._repo = repository

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_application(
        self,
        user: AuthenticatedUser,
        *,
        tenant_id: TenantId | UUID,
        los_reference: str | None = None,
        loan_number: str | None = None,
    ) -> MortgageApplication:
        """
        Create a new mortgage application in DRAFT state.

        The caller must hold ``write:application`` permission.

        In most integrations the application record in MIL is created when
        a mortgage professional begins attaching documents for review. The
        LOS reference is supplied when the MIL record is associated with an
        existing LOS application; it may be provided later via ``update()``.

        Args:
            user: The authenticated principal performing the action.
            tenant_id: The institution the application belongs to.
            los_reference: Optional LOS application identifier.
            loan_number: Optional lender loan identifier.

        Returns:
            The newly created ``MortgageApplication`` in DRAFT state.

        Raises:
            AuthorizationError: If the user lacks ``write:application``.
        """
        require_permission(user, Permission.WRITE_APPLICATION)

        application = MortgageApplication.create(
            tenant_id=tenant_id,
            created_by=user.user_id,
            los_reference=los_reference,
            loan_number=loan_number,
        )
        self._repo.save(application, actor=user)
        return application

    # ------------------------------------------------------------------
    # Add party
    # ------------------------------------------------------------------

    def add_party(
        self,
        user: AuthenticatedUser,
        *,
        application_id: ApplicationId | UUID,
        party_type: PartyType,
        display_name: str,
    ) -> Party:
        """
        Add a party to a mortgage application.

        The caller must hold ``write:party`` permission.

        Args:
            user: The authenticated principal performing the action.
            application_id: The application to add the party to.
            party_type: The party's role in the application.
            display_name: A non-PII label (e.g. "Primary Borrower").

        Returns:
            The newly created ``Party``.

        Raises:
            AuthorizationError: If the user lacks ``write:party``.
            NotFoundError: If the application does not exist.
            ConflictError: If the application is WITHDRAWN.
            ValidationError: If ``display_name`` is empty.
        """
        require_permission(user, Permission.WRITE_PARTY)

        application = self._require_application(application_id)
        party = application.add_party(party_type=party_type, display_name=display_name)
        self._repo.save(application, actor=user)
        return party

    # ------------------------------------------------------------------
    # Remove party
    # ------------------------------------------------------------------

    def remove_party(
        self,
        user: AuthenticatedUser,
        *,
        application_id: ApplicationId | UUID,
        party_id: UUID,
    ) -> None:
        """
        Remove a party from a mortgage application.

        The caller must hold ``write:party`` permission.

        Args:
            user: The authenticated principal performing the action.
            application_id: The application to remove the party from.
            party_id: The ID of the party to remove.

        Raises:
            AuthorizationError: If the user lacks ``write:party``.
            NotFoundError: If the application or party does not exist.
            ConflictError: If the application is in a terminal state.
        """
        require_permission(user, Permission.WRITE_PARTY)

        application = self._require_application(application_id)
        application.remove_party(party_id)
        self._repo.save(application, actor=user)

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def submit_application(
        self,
        user: AuthenticatedUser,
        *,
        application_id: ApplicationId | UUID,
    ) -> MortgageApplication:
        """
        Submit an application for intelligence review (DRAFT → SUBMITTED).

        The caller must hold ``write:application`` permission. At least one
        APPLICANT party must be registered before submission.

        Raises:
            AuthorizationError: If the user lacks ``write:application``.
            NotFoundError: If the application does not exist.
            ConflictError: If there are no APPLICANT parties.
            InvalidStateTransitionError: If the application is not in DRAFT state.
        """
        require_permission(user, Permission.WRITE_APPLICATION)

        application = self._require_application(application_id)
        application.submit()
        self._repo.save(application, actor=user)
        return application

    def withdraw_application(
        self,
        user: AuthenticatedUser,
        *,
        application_id: ApplicationId | UUID,
    ) -> MortgageApplication:
        """
        Withdraw an application (any non-terminal state → WITHDRAWN).

        Raises:
            AuthorizationError: If the user lacks ``write:application``.
            NotFoundError: If the application does not exist.
            InvalidStateTransitionError: If already in a terminal state.
        """
        require_permission(user, Permission.WRITE_APPLICATION)

        application = self._require_application(application_id)
        application.withdraw()
        self._repo.save(application, actor=user)
        return application

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_application(
        self,
        user: AuthenticatedUser,
        *,
        application_id: ApplicationId | UUID,
    ) -> MortgageApplication:
        """
        Retrieve an application by ID.

        Raises:
            AuthorizationError: If the user lacks ``read:application``.
            NotFoundError: If the application does not exist.
        """
        require_permission(user, Permission.READ_APPLICATION)
        return self._require_application(application_id)

    def list_applications(
        self,
        user: AuthenticatedUser,
        *,
        tenant_id: TenantId | UUID,
        status: str | None = None,
        search: str | None = None,
    ) -> list[MortgageApplication]:
        """
        Return all applications for a tenant, optionally filtered by status
        and/or a search term matched against LOS reference, loan number,
        application ID, or borrower display name (see
        ``ApplicationRepository.get_for_tenant`` for the exact match rules).

        Raises:
            AuthorizationError: If the user lacks ``read:application``.
        """
        require_permission(user, Permission.READ_APPLICATION)
        return self._repo.get_for_tenant(tenant_id, status=status, search=search)

    # ------------------------------------------------------------------
    # Party type validation (T036 explicit requirement)
    # ------------------------------------------------------------------

    @staticmethod
    def validate_party_type(value: str) -> PartyType:
        """
        Parse and validate a party type string supplied from the API layer.

        Converts the caller's raw string into a typed ``PartyType`` enum value.
        Centralising this here prevents invalid strings from reaching the
        aggregate and keeps validation at the service boundary.

        Args:
            value: A string representation of a party type
                (e.g. ``"APPLICANT"``).

        Returns:
            The corresponding ``PartyType`` enum member.

        Raises:
            ValidationError: If the string does not correspond to a valid
                ``PartyType`` member.
        """
        try:
            return PartyType(value.upper())
        except ValueError as exc:
            valid = ", ".join(pt.value for pt in PartyType)
            raise ValidationError(
                f"Invalid party type {value!r}. Valid values: {valid}",
                field="party_type",
            ) from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_application(self, application_id: ApplicationId | UUID) -> MortgageApplication:
        application = self._repo.get_by_id(application_id)
        if application is None:
            raise NotFoundError("MortgageApplication", application_id)
        return application

    # ------------------------------------------------------------------
    # Convenience: combined party_type validation + add
    # ------------------------------------------------------------------

    def add_party_by_type_string(
        self,
        user: AuthenticatedUser,
        *,
        application_id: ApplicationId | UUID,
        party_type_str: str,
        display_name: str,
    ) -> Party:
        """
        Validate party type string and add the party in a single call.

        This is the entry point used by API route handlers which receive raw
        strings from request bodies. It combines ``validate_party_type()`` and
        ``add_party()`` to provide a clean single-call API for the transport
        layer.

        Raises:
            ValidationError: If the party type string is not valid.
            (All other exceptions from ``add_party`` apply.)
        """
        party_type = self.validate_party_type(party_type_str)
        return self.add_party(
            user,
            application_id=application_id,
            party_type=party_type,
            display_name=display_name,
        )
