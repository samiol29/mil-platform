"""Unit tests for mil.application.models — PartyType, ApplicationStatus, MortgageApplication, Party."""

from __future__ import annotations

from uuid import uuid4

import pytest

from mil.application.models import (
    _TERMINAL_STATES,
    _VALID_TRANSITIONS,
    ApplicationStatus,
    MortgageApplication,
    Party,
    PartyType,
)
from mil.kernel.errors import (
    ConflictError,
    InvalidStateTransitionError,
    NotFoundError,
    ValidationError,
)

# ---------------------------------------------------------------------------
# PartyType
# ---------------------------------------------------------------------------


class TestPartyType:
    def test_all_expected_members_exist(self) -> None:
        expected = {"APPLICANT", "CO_APPLICANT", "GUARANTOR", "CORPORATE_ENTITY"}
        actual = {pt.value for pt in PartyType}
        assert actual == expected

    def test_members_are_strings(self) -> None:
        for pt in PartyType:
            assert isinstance(pt, str)

    def test_lookup_by_value(self) -> None:
        assert PartyType("APPLICANT") is PartyType.APPLICANT
        assert PartyType("GUARANTOR") is PartyType.GUARANTOR

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            PartyType("INVALID_TYPE")

    def test_values_match_names(self) -> None:
        for pt in PartyType:
            assert pt.value == pt.name

    def test_is_str_subtype(self) -> None:
        assert issubclass(PartyType, str)

    def test_equality_with_plain_string(self) -> None:
        assert PartyType.APPLICANT == "APPLICANT"
        assert PartyType.CO_APPLICANT == "CO_APPLICANT"


# ---------------------------------------------------------------------------
# ApplicationStatus state machine
# ---------------------------------------------------------------------------


class TestApplicationStatus:
    def test_all_expected_statuses(self) -> None:
        expected = {"DRAFT", "SUBMITTED", "IN_REVIEW", "REVIEW_COMPLETE", "WITHDRAWN"}
        assert {s.value for s in ApplicationStatus} == expected

    def test_terminal_states(self) -> None:
        assert ApplicationStatus.REVIEW_COMPLETE in _TERMINAL_STATES
        assert ApplicationStatus.WITHDRAWN in _TERMINAL_STATES

    def test_non_terminal_states_have_transitions(self) -> None:
        non_terminal = set(ApplicationStatus) - _TERMINAL_STATES
        for state in non_terminal:
            assert state in _VALID_TRANSITIONS, f"{state} should have valid transitions"

    def test_draft_can_transition_to_submitted_and_withdrawn(self) -> None:
        allowed = _VALID_TRANSITIONS[ApplicationStatus.DRAFT]
        assert ApplicationStatus.SUBMITTED in allowed
        assert ApplicationStatus.WITHDRAWN in allowed

    def test_submitted_can_transition_to_in_review_and_withdrawn(self) -> None:
        allowed = _VALID_TRANSITIONS[ApplicationStatus.SUBMITTED]
        assert ApplicationStatus.IN_REVIEW in allowed
        assert ApplicationStatus.WITHDRAWN in allowed

    def test_in_review_can_transition_to_review_complete_and_withdrawn(self) -> None:
        allowed = _VALID_TRANSITIONS[ApplicationStatus.IN_REVIEW]
        assert ApplicationStatus.REVIEW_COMPLETE in allowed
        assert ApplicationStatus.WITHDRAWN in allowed

    def test_terminal_states_not_in_valid_transitions(self) -> None:
        for terminal in _TERMINAL_STATES:
            assert terminal not in _VALID_TRANSITIONS


# ---------------------------------------------------------------------------
# MortgageApplication — factory and basic properties
# ---------------------------------------------------------------------------


def _make_application(
    *,
    los_reference: str | None = None,
    loan_number: str | None = None,
) -> MortgageApplication:
    return MortgageApplication.create(
        tenant_id=uuid4(),
        created_by=uuid4(),
        los_reference=los_reference,
        loan_number=loan_number,
    )


class TestMortgageApplicationCreate:
    def test_create_returns_application(self) -> None:
        app = _make_application()
        assert isinstance(app, MortgageApplication)

    def test_initial_status_is_draft(self) -> None:
        app = _make_application()
        assert app.status == ApplicationStatus.DRAFT

    def test_id_is_uuid(self) -> None:
        from uuid import UUID

        app = _make_application()
        assert isinstance(app.id, UUID)

    def test_two_applications_have_different_ids(self) -> None:
        assert _make_application().id != _make_application().id

    def test_los_reference_stored(self) -> None:
        app = _make_application(los_reference="LOS-REF-001")
        assert app.los_reference == "LOS-REF-001"

    def test_los_reference_optional(self) -> None:
        app = _make_application()
        assert app.los_reference is None

    def test_loan_number_stored(self) -> None:
        app = _make_application(loan_number="LN-REF-001")
        assert app.loan_number == "LN-REF-001"

    def test_loan_number_optional(self) -> None:
        app = _make_application()
        assert app.loan_number is None

    def test_created_at_is_timezone_aware(self) -> None:
        app = _make_application()
        assert app.created_at.tzinfo is not None

    def test_updated_at_is_timezone_aware(self) -> None:
        app = _make_application()
        assert app.updated_at.tzinfo is not None

    def test_parties_initially_empty(self) -> None:
        app = _make_application()
        assert app.parties == []

    def test_create_enqueues_application_created_event(self) -> None:
        app = _make_application()
        events = app.collect_pending_events()
        assert len(events) == 1
        assert events[0]["event_type"] == "APPLICATION_CREATED"
        assert events[0]["entity_type"] == "APPLICATION"

    def test_collect_pending_events_clears_queue(self) -> None:
        app = _make_application()
        app.collect_pending_events()
        assert app.collect_pending_events() == []

    def test_repr_contains_useful_info(self) -> None:
        app = _make_application()
        r = repr(app)
        assert "MortgageApplication" in r
        assert "DRAFT" in r


# ---------------------------------------------------------------------------
# MortgageApplication.add_party
# ---------------------------------------------------------------------------


class TestAddParty:
    def test_add_applicant(self) -> None:
        app = _make_application()
        app.collect_pending_events()
        party = app.add_party(PartyType.APPLICANT, "Primary Borrower")
        assert party.party_type == "APPLICANT"
        assert party.display_name == "Primary Borrower"
        assert party in app.parties

    def test_add_co_applicant(self) -> None:
        app = _make_application()
        app.collect_pending_events()
        party = app.add_party(PartyType.CO_APPLICANT, "Joint Borrower")
        assert party.party_type == "CO_APPLICANT"

    def test_add_guarantor(self) -> None:
        app = _make_application()
        app.collect_pending_events()
        party = app.add_party(PartyType.GUARANTOR, "Security Provider")
        assert party.party_type == "GUARANTOR"

    def test_add_corporate_entity(self) -> None:
        app = _make_application()
        app.collect_pending_events()
        party = app.add_party(PartyType.CORPORATE_ENTITY, "Borrowing Company Ltd")
        assert party.party_type == "CORPORATE_ENTITY"

    def test_multiple_parties_allowed(self) -> None:
        app = _make_application()
        app.collect_pending_events()
        app.add_party(PartyType.APPLICANT, "Borrower A")
        app.add_party(PartyType.CO_APPLICANT, "Borrower B")
        assert len(app.parties) == 2

    def test_add_party_enqueues_party_added_event(self) -> None:
        app = _make_application()
        app.collect_pending_events()
        app.add_party(PartyType.APPLICANT, "Primary Borrower")
        events = app.collect_pending_events()
        assert len(events) == 1
        assert events[0]["event_type"] == "PARTY_ADDED"
        assert events[0]["entity_type"] == "PARTY"

    def test_party_added_event_data_contains_type(self) -> None:
        app = _make_application()
        app.collect_pending_events()
        app.add_party(PartyType.APPLICANT, "Primary Borrower")
        events = app.collect_pending_events()
        assert events[0]["data"]["party_type"] == "APPLICANT"  # type: ignore[index]

    def test_add_party_to_withdrawn_raises_conflict(self) -> None:
        app = _make_application()
        app.collect_pending_events()
        app.status = ApplicationStatus.WITHDRAWN
        with pytest.raises(ConflictError, match="WITHDRAWN"):
            app.add_party(PartyType.APPLICANT, "Late Borrower")

    def test_add_party_empty_display_name_raises_validation_error(self) -> None:
        app = _make_application()
        with pytest.raises(ValidationError, match="display_name"):
            app.add_party(PartyType.APPLICANT, "")

    def test_add_party_whitespace_display_name_raises_validation_error(self) -> None:
        app = _make_application()
        with pytest.raises(ValidationError, match="display_name"):
            app.add_party(PartyType.APPLICANT, "   ")

    def test_display_name_is_stripped(self) -> None:
        app = _make_application()
        party = app.add_party(PartyType.APPLICANT, "  Primary Borrower  ")
        assert party.display_name == "Primary Borrower"

    def test_party_application_id_matches(self) -> None:
        app = _make_application()
        party = app.add_party(PartyType.APPLICANT, "Borrower")
        assert party.application_id == app.id

    def test_updated_at_changes_after_add_party(self) -> None:
        from time import sleep

        app = _make_application()
        original_updated_at = app.updated_at
        sleep(0.01)
        app.add_party(PartyType.APPLICANT, "Borrower")
        assert app.updated_at >= original_updated_at


# ---------------------------------------------------------------------------
# MortgageApplication.remove_party
# ---------------------------------------------------------------------------


class TestRemoveParty:
    def test_remove_existing_party(self) -> None:
        app = _make_application()
        party = app.add_party(PartyType.APPLICANT, "Borrower")
        app.collect_pending_events()
        app.remove_party(party.id)
        assert party not in app.parties

    def test_remove_enqueues_party_removed_event(self) -> None:
        app = _make_application()
        party = app.add_party(PartyType.APPLICANT, "Borrower")
        app.collect_pending_events()
        app.remove_party(party.id)
        events = app.collect_pending_events()
        assert len(events) == 1
        assert events[0]["event_type"] == "PARTY_REMOVED"

    def test_remove_nonexistent_party_raises_not_found(self) -> None:
        app = _make_application()
        with pytest.raises(NotFoundError):
            app.remove_party(uuid4())

    def test_remove_from_withdrawn_raises_conflict(self) -> None:
        app = _make_application()
        party = app.add_party(PartyType.APPLICANT, "Borrower")
        app.status = ApplicationStatus.WITHDRAWN
        with pytest.raises(ConflictError):
            app.remove_party(party.id)

    def test_remove_from_review_complete_raises_conflict(self) -> None:
        app = _make_application()
        party = app.add_party(PartyType.APPLICANT, "Borrower")
        app.status = ApplicationStatus.REVIEW_COMPLETE
        with pytest.raises(ConflictError):
            app.remove_party(party.id)


# ---------------------------------------------------------------------------
# MortgageApplication lifecycle transitions
# ---------------------------------------------------------------------------


class TestLifecycleTransitions:
    def test_submit_valid_application(self) -> None:
        app = _make_application()
        app.collect_pending_events()
        app.add_party(PartyType.APPLICANT, "Borrower")
        app.collect_pending_events()
        app.submit()
        assert app.status == ApplicationStatus.SUBMITTED

    def test_submit_enqueues_state_changed_event(self) -> None:
        app = _make_application()
        app.add_party(PartyType.APPLICANT, "Borrower")
        app.collect_pending_events()
        app.submit()
        events = app.collect_pending_events()
        assert any(e["event_type"] == "APPLICATION_STATE_CHANGED" for e in events)

    def test_submit_without_applicant_raises_conflict(self) -> None:
        app = _make_application()
        app.add_party(PartyType.CO_APPLICANT, "Co-Borrower")
        with pytest.raises(ConflictError, match="APPLICANT"):
            app.submit()

    def test_submit_empty_application_raises_conflict(self) -> None:
        app = _make_application()
        with pytest.raises(ConflictError, match="APPLICANT"):
            app.submit()

    def test_start_review_from_submitted(self) -> None:
        app = _make_application()
        app.add_party(PartyType.APPLICANT, "Borrower")
        app.submit()
        app.collect_pending_events()
        app.start_review()
        assert app.status == ApplicationStatus.IN_REVIEW

    def test_complete_review_from_in_review(self) -> None:
        app = _make_application()
        app.add_party(PartyType.APPLICANT, "Borrower")
        app.submit()
        app.start_review()
        app.collect_pending_events()
        app.complete_review()
        assert app.status == ApplicationStatus.REVIEW_COMPLETE

    def test_withdraw_from_draft(self) -> None:
        app = _make_application()
        app.collect_pending_events()
        app.withdraw()
        assert app.status == ApplicationStatus.WITHDRAWN

    def test_withdraw_from_submitted(self) -> None:
        app = _make_application()
        app.add_party(PartyType.APPLICANT, "Borrower")
        app.submit()
        app.collect_pending_events()
        app.withdraw()
        assert app.status == ApplicationStatus.WITHDRAWN

    def test_withdraw_from_in_review(self) -> None:
        app = _make_application()
        app.add_party(PartyType.APPLICANT, "Borrower")
        app.submit()
        app.start_review()
        app.collect_pending_events()
        app.withdraw()
        assert app.status == ApplicationStatus.WITHDRAWN

    def test_cannot_submit_withdrawn_application(self) -> None:
        app = _make_application()
        app.add_party(PartyType.APPLICANT, "Borrower")
        app.withdraw()
        with pytest.raises(InvalidStateTransitionError):
            app.submit()

    def test_cannot_withdraw_completed_application(self) -> None:
        app = _make_application()
        app.add_party(PartyType.APPLICANT, "Borrower")
        app.submit()
        app.start_review()
        app.complete_review()
        with pytest.raises(InvalidStateTransitionError):
            app.withdraw()

    def test_invalid_transition_error_includes_states(self) -> None:
        app = _make_application()
        app.add_party(PartyType.APPLICANT, "Borrower")
        app.submit()
        app.start_review()
        app.complete_review()
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            app.withdraw()
        assert "REVIEW_COMPLETE" in str(exc_info.value)
        assert "WITHDRAWN" in str(exc_info.value)

    def test_state_changed_event_includes_from_and_to(self) -> None:
        app = _make_application()
        app.add_party(PartyType.APPLICANT, "Borrower")
        app.collect_pending_events()
        app.submit()
        events = app.collect_pending_events()
        state_event = next(e for e in events if e["event_type"] == "APPLICATION_STATE_CHANGED")
        data = state_event["data"]  # type: ignore[index]
        assert data["from_status"] == "DRAFT"  # type: ignore[index]
        assert data["to_status"] == "SUBMITTED"  # type: ignore[index]


# ---------------------------------------------------------------------------
# MortgageApplication.applicant_parties property
# ---------------------------------------------------------------------------


class TestApplicantPartiesProperty:
    def test_returns_only_applicants(self) -> None:
        app = _make_application()
        app.add_party(PartyType.APPLICANT, "Borrower A")
        app.add_party(PartyType.CO_APPLICANT, "Borrower B")
        app.add_party(PartyType.GUARANTOR, "Guarantor C")
        assert len(app.applicant_parties) == 1
        assert app.applicant_parties[0].party_type == "APPLICANT"

    def test_empty_when_no_applicants(self) -> None:
        app = _make_application()
        app.add_party(PartyType.CO_APPLICANT, "Co-Borrower")
        assert app.applicant_parties == []


# ---------------------------------------------------------------------------
# Party ORM model (standalone)
# ---------------------------------------------------------------------------


class TestPartyModel:
    def test_tablename(self) -> None:
        assert Party.__tablename__ == "parties"

    def test_schema(self) -> None:
        assert Party.__table_args__["schema"] == "core"

    def test_party_type_enum_property(self) -> None:
        party = Party(
            id=uuid4(),
            application_id=uuid4(),
            party_type="APPLICANT",
            display_name="Borrower",
        )
        assert party.party_type_enum is PartyType.APPLICANT

    def test_repr_contains_useful_info(self) -> None:
        party = Party(
            id=uuid4(),
            application_id=uuid4(),
            party_type="GUARANTOR",
            display_name="Guarantor",
        )
        assert "Party" in repr(party)
        assert "GUARANTOR" in repr(party)


# ---------------------------------------------------------------------------
# MortgageApplication ORM model metadata
# ---------------------------------------------------------------------------


class TestMortgageApplicationORM:
    def test_tablename(self) -> None:
        assert MortgageApplication.__tablename__ == "applications"

    def test_schema(self) -> None:
        assert MortgageApplication.__table_args__["schema"] == "core"

    def test_status_enum_property(self) -> None:
        app = _make_application()
        assert app.status_enum is ApplicationStatus.DRAFT
