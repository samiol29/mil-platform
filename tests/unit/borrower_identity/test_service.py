"""Unit tests for mil.borrower_identity.service — BorrowerIdentityService."""

from __future__ import annotations

from uuid import uuid4

import pytest

from mil.borrower_identity.models import (
    BorrowerIdentity,
    BorrowerIdentityMember,
    IdentityMatchCandidate,
)
from mil.borrower_identity.service import BorrowerIdentityService, PartyMatchInput
from mil.kernel.errors import AuthorizationError
from mil.kernel.security import AuthenticatedUser, Role


class FakeBorrowerIdentityRepository:
    def __init__(self) -> None:
        self.candidates: dict[object, IdentityMatchCandidate] = {}
        self.identities: dict[object, BorrowerIdentity] = {}
        self.members: list[BorrowerIdentityMember] = []

    def save_candidate(self, candidate: IdentityMatchCandidate) -> None:
        self.candidates[candidate.id] = candidate

    def get_candidate_by_id(self, candidate_id: object) -> IdentityMatchCandidate | None:
        return self.candidates.get(candidate_id)

    def get_candidates_for_party(self, party_id: object) -> list[IdentityMatchCandidate]:
        return [c for c in self.candidates.values() if c.party_id == party_id]

    def get_pending_candidate(self, party_id: object, candidate_party_id: object):
        for c in self.candidates.values():
            if (
                c.party_id == party_id
                and c.candidate_party_id == candidate_party_id
                and c.status == "PENDING"
            ):
                return c
        return None

    def save_identity(self, identity: BorrowerIdentity) -> None:
        self.identities[identity.id] = identity

    def get_identity_by_id(self, identity_id: object) -> BorrowerIdentity | None:
        return self.identities.get(identity_id)

    def save_member(self, member: BorrowerIdentityMember) -> None:
        self.members.append(member)

    def get_active_member_for_party(self, party_id: object) -> BorrowerIdentityMember | None:
        for m in self.members:
            if m.party_id == party_id and m.unlinked_at is None:
                return m
        return None

    def get_active_members_for_identity(self, identity_id: object) -> list[BorrowerIdentityMember]:
        return [
            m
            for m in self.members
            if m.borrower_identity_id == identity_id and m.unlinked_at is None
        ]


class FakeAuditWriter:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record(self, **kwargs: object) -> object:
        self.records.append(kwargs)
        return object()


def _make_service() -> tuple[
    BorrowerIdentityService, FakeBorrowerIdentityRepository, FakeAuditWriter
]:
    repo = FakeBorrowerIdentityRepository()
    audit = FakeAuditWriter()
    return BorrowerIdentityService(repo, audit), repo, audit  # type: ignore[arg-type]


def _underwriter(tenant_id: object) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(), tenant_id=tenant_id, roles=frozenset({Role.UNDERWRITER})
    )


def _readonly_caller(tenant_id: object) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(), tenant_id=tenant_id, roles=frozenset({Role.AUDIT_TEAM})
    )


class TestComputeCandidates:
    def test_deterministic_match_on_identifier_hash(self) -> None:
        service, _repo, _audit = _make_service()
        tenant_id = uuid4()
        caller = _underwriter(tenant_id)
        app_a, app_b = uuid4(), uuid4()
        subject = PartyMatchInput(
            party_id=uuid4(),
            application_id=app_a,
            display_name="Jane Smith",
            external_identifier_hash="abc123",
            identifier_type="CUSTOMER_ID",
        )
        other = PartyMatchInput(
            party_id=uuid4(),
            application_id=app_b,
            display_name="J Smith",
            external_identifier_hash="abc123",
            identifier_type="CUSTOMER_ID",
        )
        candidates = service.compute_candidates(
            caller, tenant_id=tenant_id, subject=subject, others=[other]
        )
        assert len(candidates) == 1
        assert candidates[0].match_score == 0.98
        assert candidates[0].match_basis["exact_identifier_match"] is True

    def test_probabilistic_match_on_normalized_name(self) -> None:
        service, _repo, _audit = _make_service()
        tenant_id = uuid4()
        caller = _underwriter(tenant_id)
        subject = PartyMatchInput(
            party_id=uuid4(), application_id=uuid4(), display_name="Jane  Smith."
        )
        other = PartyMatchInput(party_id=uuid4(), application_id=uuid4(), display_name="jane smith")
        candidates = service.compute_candidates(
            caller, tenant_id=tenant_id, subject=subject, others=[other]
        )
        assert len(candidates) == 1
        assert candidates[0].match_score == 0.65
        assert candidates[0].match_basis == {"name_similarity": "exact_normalized_match"}

    def test_no_match_when_no_real_signal(self) -> None:
        service, _repo, _audit = _make_service()
        tenant_id = uuid4()
        caller = _underwriter(tenant_id)
        subject = PartyMatchInput(
            party_id=uuid4(), application_id=uuid4(), display_name="Jane Smith"
        )
        other = PartyMatchInput(party_id=uuid4(), application_id=uuid4(), display_name="John Doe")
        candidates = service.compute_candidates(
            caller, tenant_id=tenant_id, subject=subject, others=[other]
        )
        assert candidates == []

    def test_skips_same_application(self) -> None:
        service, _repo, _audit = _make_service()
        tenant_id = uuid4()
        caller = _underwriter(tenant_id)
        shared_app = uuid4()
        subject = PartyMatchInput(
            party_id=uuid4(), application_id=shared_app, display_name="Jane Smith"
        )
        other = PartyMatchInput(
            party_id=uuid4(), application_id=shared_app, display_name="Jane Smith"
        )
        candidates = service.compute_candidates(
            caller, tenant_id=tenant_id, subject=subject, others=[other]
        )
        assert candidates == []

    def test_skips_existing_pending_candidate(self) -> None:
        service, _repo, _audit = _make_service()
        tenant_id = uuid4()
        caller = _underwriter(tenant_id)
        subject = PartyMatchInput(
            party_id=uuid4(), application_id=uuid4(), display_name="Jane Smith"
        )
        other = PartyMatchInput(party_id=uuid4(), application_id=uuid4(), display_name="Jane Smith")
        first = service.compute_candidates(
            caller, tenant_id=tenant_id, subject=subject, others=[other]
        )
        second = service.compute_candidates(
            caller, tenant_id=tenant_id, subject=subject, others=[other]
        )
        assert len(first) == 1
        assert second == []

    def test_readonly_role_forbidden(self) -> None:
        service, _repo, _audit = _make_service()
        caller = _readonly_caller(uuid4())
        with pytest.raises(AuthorizationError):
            service.compute_candidates(
                caller,
                tenant_id=uuid4(),
                subject=PartyMatchInput(party_id=uuid4(), application_id=uuid4(), display_name="X"),
                others=[],
            )


class TestConfirmMatch:
    def test_confirm_creates_new_identity(self) -> None:
        service, repo, audit = _make_service()
        tenant_id = uuid4()
        caller = _underwriter(tenant_id)
        candidate = IdentityMatchCandidate.create(
            tenant_id=tenant_id,
            party_id=uuid4(),
            candidate_party_id=uuid4(),
            match_score=0.98,
            match_basis={"exact_identifier_match": True},
        )
        repo.save_candidate(candidate)

        identity = service.confirm_match(caller, candidate)

        assert candidate.status == "CONFIRMED"
        assert identity.tenant_id == tenant_id
        assert audit.records[-1]["event_type"] == "IDENTITY_MATCH_CONFIRMED"

    def test_confirm_reuses_existing_identity_for_already_linked_party(self) -> None:
        service, repo, _audit = _make_service()
        tenant_id = uuid4()
        caller = _underwriter(tenant_id)
        party_id = uuid4()
        application_id = uuid4()

        existing_identity = BorrowerIdentity.create(
            tenant_id=tenant_id, primary_display_name="Jane"
        )
        repo.save_identity(existing_identity)
        existing_member = BorrowerIdentityMember.create(
            borrower_identity_id=existing_identity.id,
            party_id=party_id,
            application_id=application_id,
            linked_by_user_id=caller.user_id,
        )
        repo.save_member(existing_member)

        candidate = IdentityMatchCandidate.create(
            tenant_id=tenant_id,
            party_id=party_id,
            candidate_party_id=uuid4(),
            match_score=0.98,
            match_basis={},
        )
        repo.save_candidate(candidate)

        identity = service.confirm_match(caller, candidate)
        assert identity.id == existing_identity.id


class TestRejectMatch:
    def test_reject_records_reason(self) -> None:
        service, repo, audit = _make_service()
        tenant_id = uuid4()
        caller = _underwriter(tenant_id)
        candidate = IdentityMatchCandidate.create(
            tenant_id=tenant_id,
            party_id=uuid4(),
            candidate_party_id=uuid4(),
            match_score=0.65,
            match_basis={},
        )
        repo.save_candidate(candidate)

        rejected = service.reject_match(caller, candidate, reason="Not the same person")
        assert rejected.status == "REJECTED"
        assert audit.records[-1]["event_type"] == "IDENTITY_MATCH_REJECTED"


class TestLinkMember:
    def test_link_member_creates_when_absent(self) -> None:
        service, repo, _audit = _make_service()
        caller = _underwriter(uuid4())
        identity = BorrowerIdentity.create(tenant_id=uuid4(), primary_display_name="Jane")
        repo.save_identity(identity)

        member = service.link_member(
            caller, identity=identity, party_id=uuid4(), application_id=uuid4()
        )
        assert member in repo.members

    def test_link_member_returns_existing_when_already_active(self) -> None:
        service, repo, _audit = _make_service()
        caller = _underwriter(uuid4())
        identity = BorrowerIdentity.create(tenant_id=uuid4(), primary_display_name="Jane")
        repo.save_identity(identity)
        party_id = uuid4()
        existing = BorrowerIdentityMember.create(
            borrower_identity_id=identity.id,
            party_id=party_id,
            application_id=uuid4(),
            linked_by_user_id=caller.user_id,
        )
        repo.save_member(existing)

        member = service.link_member(
            caller, identity=identity, party_id=party_id, application_id=uuid4()
        )
        assert member is existing
        assert len(repo.members) == 1
