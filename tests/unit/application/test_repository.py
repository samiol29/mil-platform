"""Unit tests for mil.application.repository — ApplicationRepository."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from mil.application.models import MortgageApplication, PartyType
from mil.application.repository import ApplicationRepository
from mil.audit.writer import AuditWriter
from mil.kernel.security import AuthenticatedUser, Role
from mil.kernel.types import TenantId, UserId

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=UserId(uuid4()),
        tenant_id=TenantId(uuid4()),
        roles=frozenset({Role.VERIFICATION_OFFICER}),
    )


def _make_application() -> MortgageApplication:
    return MortgageApplication.create(
        tenant_id=uuid4(),
        created_by=uuid4(),
    )


def _make_repo() -> tuple[ApplicationRepository, MagicMock, MagicMock]:
    session = MagicMock()
    audit_writer = MagicMock(spec=AuditWriter)
    return ApplicationRepository(session, audit_writer), session, audit_writer


# ---------------------------------------------------------------------------
# save() — audit event emission
# ---------------------------------------------------------------------------


class TestRepositorySave:
    def test_save_adds_application_to_session(self) -> None:
        repo, session, _ = _make_repo()
        app = _make_application()
        user = _make_user()
        repo.save(app, actor=user)
        session.add.assert_called_once_with(app)

    def test_save_calls_flush(self) -> None:
        repo, session, _ = _make_repo()
        app = _make_application()
        user = _make_user()
        repo.save(app, actor=user)
        session.flush.assert_called_once()

    def test_save_new_application_emits_created_event(self) -> None:
        repo, _, audit = _make_repo()
        app = _make_application()
        user = _make_user()
        repo.save(app, actor=user)
        call_args = audit.record.call_args_list
        event_types = [c.kwargs["event_type"] for c in call_args]
        assert "APPLICATION_CREATED" in event_types

    def test_save_emits_application_created_with_correct_entity_type(self) -> None:
        repo, _, audit = _make_repo()
        app = _make_application()
        user = _make_user()
        repo.save(app, actor=user)
        created_calls = [
            c
            for c in audit.record.call_args_list
            if c.kwargs["event_type"] == "APPLICATION_CREATED"
        ]
        assert len(created_calls) == 1
        assert created_calls[0].kwargs["entity_type"] == "APPLICATION"

    def test_save_emits_created_event_with_actor_id(self) -> None:
        repo, _, audit = _make_repo()
        app = _make_application()
        user = _make_user()
        repo.save(app, actor=user)
        created_calls = [
            c
            for c in audit.record.call_args_list
            if c.kwargs["event_type"] == "APPLICATION_CREATED"
        ]
        assert created_calls[0].kwargs["actor_id"] == user.user_id

    def test_save_application_with_party_emits_party_added(self) -> None:
        repo, _, audit = _make_repo()
        app = _make_application()
        app.collect_pending_events()  # clear APPLICATION_CREATED
        app.add_party(PartyType.APPLICANT, "Borrower")
        user = _make_user()
        repo.save(app, actor=user)
        event_types = [c.kwargs["event_type"] for c in audit.record.call_args_list]
        assert "PARTY_ADDED" in event_types

    def test_save_clears_pending_events_after_flush(self) -> None:
        repo, _, _ = _make_repo()
        app = _make_application()
        user = _make_user()
        repo.save(app, actor=user)
        # After save, pending events should be drained
        assert app.collect_pending_events() == []

    def test_save_with_no_events_calls_no_audit_records(self) -> None:
        repo, _, audit = _make_repo()
        app = _make_application()
        # Drain pending events manually before saving
        app.collect_pending_events()
        user = _make_user()
        repo.save(app, actor=user)
        audit.record.assert_not_called()

    def test_state_change_emits_state_changed_audit_event(self) -> None:
        repo, _, audit = _make_repo()
        app = _make_application()
        app.add_party(PartyType.APPLICANT, "Borrower")
        app.submit()
        app.collect_pending_events()  # clear previous events
        app.withdraw()
        user = _make_user()
        repo.save(app, actor=user)
        event_types = [c.kwargs["event_type"] for c in audit.record.call_args_list]
        assert "APPLICATION_STATE_CHANGED" in event_types


# ---------------------------------------------------------------------------
# get_by_id()
# ---------------------------------------------------------------------------


class TestRepositoryGetById:
    def test_get_by_id_calls_session_get(self) -> None:
        repo, session, _ = _make_repo()
        app_id = uuid4()
        repo.get_by_id(app_id)
        session.get.assert_called_once_with(MortgageApplication, app_id)

    def test_get_by_id_returns_none_when_not_found(self) -> None:
        repo, session, _ = _make_repo()
        session.get.return_value = None
        result = repo.get_by_id(uuid4())
        assert result is None

    def test_get_by_id_returns_application_when_found(self) -> None:
        repo, session, _ = _make_repo()
        app = _make_application()
        session.get.return_value = app
        result = repo.get_by_id(app.id)
        assert result is app

    def test_exists_returns_false_when_not_found(self) -> None:
        repo, session, _ = _make_repo()
        session.get.return_value = None
        assert repo.exists(uuid4()) is False

    def test_exists_returns_true_when_found(self) -> None:
        repo, session, _ = _make_repo()
        session.get.return_value = _make_application()
        assert repo.exists(uuid4()) is True


# ---------------------------------------------------------------------------
# get_for_tenant()
# ---------------------------------------------------------------------------


class TestRepositoryGetForTenant:
    def test_get_for_tenant_queries_session(self) -> None:
        repo, session, _ = _make_repo()
        tenant_id = uuid4()
        session.scalars.return_value = iter([])
        result = repo.get_for_tenant(tenant_id)
        assert result == []
        session.scalars.assert_called_once()

    def test_get_for_tenant_returns_list(self) -> None:
        repo, session, _ = _make_repo()
        app1 = _make_application()
        app2 = _make_application()
        session.scalars.return_value = iter([app1, app2])
        result = repo.get_for_tenant(uuid4())
        assert result == [app1, app2]

    def test_search_none_adds_no_ilike_clause(self) -> None:
        repo, session, _ = _make_repo()
        session.scalars.return_value = iter([])
        repo.get_for_tenant(uuid4())
        stmt = session.scalars.call_args.args[0]
        compiled = str(
            stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        )
        assert "ILIKE" not in compiled.upper()

    def test_search_adds_ilike_clause_over_los_reference_and_loan_number(self) -> None:
        repo, session, _ = _make_repo()
        session.scalars.return_value = iter([])
        repo.get_for_tenant(uuid4(), search="Alvarez")
        stmt = session.scalars.call_args.args[0]
        compiled = str(
            stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        )
        assert "ILIKE" in compiled.upper()
        assert "%Alvarez%" in compiled
        assert "los_reference" in compiled
        assert "loan_number" in compiled

    def test_search_matches_against_party_display_name_via_exists(self) -> None:
        repo, session, _ = _make_repo()
        session.scalars.return_value = iter([])
        repo.get_for_tenant(uuid4(), search="Alvarez")
        stmt = session.scalars.call_args.args[0]
        compiled = str(
            stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        )
        assert "EXISTS" in compiled.upper()
        assert "display_name" in compiled

    def test_search_and_status_both_applied(self) -> None:
        repo, session, _ = _make_repo()
        session.scalars.return_value = iter([])
        repo.get_for_tenant(uuid4(), status="DRAFT", search="Alvarez")
        stmt = session.scalars.call_args.args[0]
        compiled = str(
            stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        )
        assert "ILIKE" in compiled.upper()
        assert "'DRAFT'" in compiled
