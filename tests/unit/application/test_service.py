"""Unit tests for mil.application.service — ApplicationService."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from mil.application.models import ApplicationStatus, MortgageApplication, PartyType
from mil.application.repository import ApplicationRepository
from mil.application.service import ApplicationService
from mil.kernel.errors import AuthorizationError, NotFoundError, ValidationError
from mil.kernel.security import AuthenticatedUser, Role
from mil.kernel.types import TenantId, UserId

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(*roles: str) -> AuthenticatedUser:
    if not roles:
        roles = (Role.VERIFICATION_OFFICER,)
    return AuthenticatedUser(
        user_id=UserId(uuid4()),
        tenant_id=TenantId(uuid4()),
        roles=frozenset(roles),
    )


def _make_admin() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=UserId(uuid4()),
        tenant_id=TenantId(uuid4()),
        roles=frozenset({Role.ADMIN}),
    )


def _make_service() -> tuple[ApplicationService, MagicMock]:
    repo = MagicMock(spec=ApplicationRepository)
    return ApplicationService(repo), repo


def _make_application(
    tenant_id=None,
    created_by=None,
) -> MortgageApplication:
    return MortgageApplication.create(
        tenant_id=tenant_id or uuid4(),
        created_by=created_by or uuid4(),
    )


# ---------------------------------------------------------------------------
# create_application
# ---------------------------------------------------------------------------


class TestCreateApplication:
    def test_create_returns_application(self) -> None:
        service, _ = _make_service()
        user = _make_admin()
        app = service.create_application(user, tenant_id=uuid4())
        assert isinstance(app, MortgageApplication)

    def test_create_status_is_draft(self) -> None:
        service, _ = _make_service()
        user = _make_admin()
        app = service.create_application(user, tenant_id=uuid4())
        assert app.status == ApplicationStatus.DRAFT

    def test_create_calls_repo_save(self) -> None:
        service, repo = _make_service()
        user = _make_admin()
        app = service.create_application(user, tenant_id=uuid4())
        repo.save.assert_called_once()
        (saved_app,) = repo.save.call_args[0]
        assert saved_app is app

    def test_create_stores_los_reference(self) -> None:
        service, _ = _make_service()
        user = _make_admin()
        app = service.create_application(user, tenant_id=uuid4(), los_reference="LOS-001")
        assert app.los_reference == "LOS-001"

    def test_create_stores_loan_number(self) -> None:
        service, _ = _make_service()
        user = _make_admin()
        app = service.create_application(user, tenant_id=uuid4(), loan_number="LN-001")
        assert app.loan_number == "LN-001"

    def test_create_requires_write_application_permission(self) -> None:
        service, _ = _make_service()
        # AUDIT_TEAM has read:application but not write:application
        user = AuthenticatedUser(
            user_id=UserId(uuid4()),
            tenant_id=TenantId(uuid4()),
            roles=frozenset({Role.AUDIT_TEAM}),
        )
        with pytest.raises(AuthorizationError):
            service.create_application(user, tenant_id=uuid4())

    def test_create_allowed_with_admin_permission(self) -> None:
        service, _ = _make_service()
        # ADMIN has the super-permission which grants all permissions
        user = AuthenticatedUser(
            user_id=UserId(uuid4()),
            tenant_id=TenantId(uuid4()),
            roles=frozenset({Role.ADMIN}),
        )
        app = service.create_application(user, tenant_id=uuid4())
        assert app is not None

    def test_create_sets_created_by_to_user_id(self) -> None:
        service, _ = _make_service()
        user = _make_admin()
        app = service.create_application(user, tenant_id=uuid4())
        assert app.created_by == user.user_id


# ---------------------------------------------------------------------------
# add_party
# ---------------------------------------------------------------------------


class TestAddParty:
    def test_add_party_returns_party(self) -> None:
        service, repo = _make_service()
        user = _make_admin()
        app = _make_application()
        repo.get_by_id.return_value = app
        party = service.add_party(
            user,
            application_id=app.id,
            party_type=PartyType.APPLICANT,
            display_name="Primary Borrower",
        )
        assert party.party_type == "APPLICANT"

    def test_add_party_persists_via_repo(self) -> None:
        service, repo = _make_service()
        user = _make_admin()
        app = _make_application()
        repo.get_by_id.return_value = app
        service.add_party(
            user,
            application_id=app.id,
            party_type=PartyType.APPLICANT,
            display_name="Primary Borrower",
        )
        repo.save.assert_called_once()

    def test_add_party_requires_write_party_permission(self) -> None:
        service, repo = _make_service()
        user = AuthenticatedUser(
            user_id=UserId(uuid4()),
            tenant_id=TenantId(uuid4()),
            roles=frozenset({Role.RISK_ANALYST}),  # no write:party
        )
        app = _make_application()
        repo.get_by_id.return_value = app
        with pytest.raises(AuthorizationError):
            service.add_party(
                user,
                application_id=app.id,
                party_type=PartyType.APPLICANT,
                display_name="Borrower",
            )

    def test_add_party_raises_not_found_when_application_missing(self) -> None:
        service, repo = _make_service()
        repo.get_by_id.return_value = None
        user = _make_admin()
        with pytest.raises(NotFoundError, match="MortgageApplication"):
            service.add_party(
                user,
                application_id=uuid4(),
                party_type=PartyType.APPLICANT,
                display_name="Borrower",
            )


# ---------------------------------------------------------------------------
# remove_party
# ---------------------------------------------------------------------------


class TestRemoveParty:
    def test_remove_party_delegates_to_aggregate(self) -> None:
        service, repo = _make_service()
        user = _make_admin()
        app = _make_application()
        party = app.add_party(PartyType.APPLICANT, "Borrower")
        app.collect_pending_events()
        repo.get_by_id.return_value = app
        service.remove_party(user, application_id=app.id, party_id=party.id)
        assert party not in app.parties

    def test_remove_party_requires_write_party_permission(self) -> None:
        service, repo = _make_service()
        user = AuthenticatedUser(
            user_id=UserId(uuid4()),
            tenant_id=TenantId(uuid4()),
            roles=frozenset({Role.RISK_ANALYST}),
        )
        app = _make_application()
        party = app.add_party(PartyType.APPLICANT, "Borrower")
        repo.get_by_id.return_value = app
        with pytest.raises(AuthorizationError):
            service.remove_party(user, application_id=app.id, party_id=party.id)

    def test_remove_party_raises_not_found_when_application_missing(self) -> None:
        service, repo = _make_service()
        repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.remove_party(_make_admin(), application_id=uuid4(), party_id=uuid4())


# ---------------------------------------------------------------------------
# submit_application
# ---------------------------------------------------------------------------


class TestSubmitApplication:
    def test_submit_transitions_to_submitted(self) -> None:
        service, repo = _make_service()
        user = _make_admin()
        app = _make_application()
        app.add_party(PartyType.APPLICANT, "Borrower")
        app.collect_pending_events()
        repo.get_by_id.return_value = app
        result = service.submit_application(user, application_id=app.id)
        assert result.status == ApplicationStatus.SUBMITTED

    def test_submit_requires_write_application_permission(self) -> None:
        service, repo = _make_service()
        user = AuthenticatedUser(
            user_id=UserId(uuid4()),
            tenant_id=TenantId(uuid4()),
            roles=frozenset({Role.AUDIT_TEAM}),
        )
        app = _make_application()
        repo.get_by_id.return_value = app
        with pytest.raises(AuthorizationError):
            service.submit_application(user, application_id=app.id)


# ---------------------------------------------------------------------------
# withdraw_application
# ---------------------------------------------------------------------------


class TestWithdrawApplication:
    def test_withdraw_transitions_to_withdrawn(self) -> None:
        service, repo = _make_service()
        user = _make_admin()
        app = _make_application()
        app.collect_pending_events()
        repo.get_by_id.return_value = app
        result = service.withdraw_application(user, application_id=app.id)
        assert result.status == ApplicationStatus.WITHDRAWN


# ---------------------------------------------------------------------------
# validate_party_type
# ---------------------------------------------------------------------------


class TestValidatePartyType:
    def test_valid_applicant(self) -> None:
        assert ApplicationService.validate_party_type("APPLICANT") is PartyType.APPLICANT

    def test_valid_co_applicant(self) -> None:
        assert ApplicationService.validate_party_type("CO_APPLICANT") is PartyType.CO_APPLICANT

    def test_valid_guarantor(self) -> None:
        assert ApplicationService.validate_party_type("GUARANTOR") is PartyType.GUARANTOR

    def test_valid_corporate_entity(self) -> None:
        assert (
            ApplicationService.validate_party_type("CORPORATE_ENTITY") is PartyType.CORPORATE_ENTITY
        )

    def test_case_insensitive(self) -> None:
        assert ApplicationService.validate_party_type("applicant") is PartyType.APPLICANT

    def test_invalid_type_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            ApplicationService.validate_party_type("BROKER")

    def test_empty_string_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            ApplicationService.validate_party_type("")

    def test_error_message_includes_valid_values(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ApplicationService.validate_party_type("UNKNOWN")
        assert "APPLICANT" in str(exc_info.value)


# ---------------------------------------------------------------------------
# add_party_by_type_string (combined validation + add)
# ---------------------------------------------------------------------------


class TestAddPartyByTypeString:
    def test_add_party_by_type_string_success(self) -> None:
        service, repo = _make_service()
        user = _make_admin()
        app = _make_application()
        repo.get_by_id.return_value = app
        party = service.add_party_by_type_string(
            user,
            application_id=app.id,
            party_type_str="APPLICANT",
            display_name="Borrower",
        )
        assert party.party_type == "APPLICANT"

    def test_add_party_by_type_string_invalid_type_raises(self) -> None:
        service, repo = _make_service()
        user = _make_admin()
        app = _make_application()
        repo.get_by_id.return_value = app
        with pytest.raises(ValidationError):
            service.add_party_by_type_string(
                user,
                application_id=app.id,
                party_type_str="INVALID",
                display_name="Borrower",
            )


# ---------------------------------------------------------------------------
# get_application / list_applications
# ---------------------------------------------------------------------------


class TestReadOperations:
    def test_get_application_requires_read_permission(self) -> None:
        service, repo = _make_service()
        user = AuthenticatedUser(
            user_id=UserId(uuid4()),
            tenant_id=TenantId(uuid4()),
            roles=frozenset(),  # no permissions
        )
        repo.get_by_id.return_value = _make_application()
        with pytest.raises(AuthorizationError):
            service.get_application(user, application_id=uuid4())

    def test_get_application_returns_application(self) -> None:
        service, repo = _make_service()
        user = AuthenticatedUser(
            user_id=UserId(uuid4()),
            tenant_id=TenantId(uuid4()),
            roles=frozenset({Role.VERIFICATION_OFFICER}),
        )
        app = _make_application()
        repo.get_by_id.return_value = app
        result = service.get_application(user, application_id=app.id)
        assert result is app

    def test_get_application_raises_not_found_when_missing(self) -> None:
        service, repo = _make_service()
        user = AuthenticatedUser(
            user_id=UserId(uuid4()),
            tenant_id=TenantId(uuid4()),
            roles=frozenset({Role.VERIFICATION_OFFICER}),
        )
        repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.get_application(user, application_id=uuid4())

    def test_list_applications_requires_read_permission(self) -> None:
        service, _repo = _make_service()
        user = AuthenticatedUser(
            user_id=UserId(uuid4()),
            tenant_id=TenantId(uuid4()),
            roles=frozenset(),
        )
        with pytest.raises(AuthorizationError):
            service.list_applications(user, tenant_id=uuid4())

    def test_list_applications_returns_list(self) -> None:
        service, repo = _make_service()
        user = AuthenticatedUser(
            user_id=UserId(uuid4()),
            tenant_id=TenantId(uuid4()),
            roles=frozenset({Role.VERIFICATION_OFFICER}),
        )
        apps = [_make_application(), _make_application()]
        repo.get_for_tenant.return_value = apps
        result = service.list_applications(user, tenant_id=uuid4())
        assert result == apps
