"""Unit tests for mil.borrower_identity.models."""

from __future__ import annotations

from uuid import uuid4

import pytest

from mil.borrower_identity.models import (
    BorrowerIdentity,
    BorrowerIdentityMember,
    IdentityMatchCandidate,
)
from mil.kernel.errors import ConflictError, ValidationError


class TestIdentityMatchCandidateCreate:
    def test_create_sets_pending_status(self) -> None:
        tenant_id, party_id, candidate_id = uuid4(), uuid4(), uuid4()
        candidate = IdentityMatchCandidate.create(
            tenant_id=tenant_id,
            party_id=party_id,
            candidate_party_id=candidate_id,
            match_score=0.98,
            match_basis={"exact_identifier_match": True},
        )
        assert candidate.status == "PENDING"
        assert candidate.match_score == 0.98
        assert candidate.reviewed_at is None

    def test_create_rejects_self_match(self) -> None:
        party_id = uuid4()
        with pytest.raises(ValidationError):
            IdentityMatchCandidate.create(
                tenant_id=uuid4(),
                party_id=party_id,
                candidate_party_id=party_id,
                match_score=0.9,
                match_basis={},
            )

    def test_create_rejects_out_of_range_score(self) -> None:
        with pytest.raises(ValidationError):
            IdentityMatchCandidate.create(
                tenant_id=uuid4(),
                party_id=uuid4(),
                candidate_party_id=uuid4(),
                match_score=1.5,
                match_basis={},
            )


class TestIdentityMatchCandidateConfirmReject:
    def test_confirm_sets_reviewed_fields(self) -> None:
        candidate = IdentityMatchCandidate.create(
            tenant_id=uuid4(),
            party_id=uuid4(),
            candidate_party_id=uuid4(),
            match_score=0.65,
            match_basis={"name_similarity": "exact_normalized_match"},
        )
        reviewer = uuid4()
        candidate.confirm(reviewer)
        assert candidate.status == "CONFIRMED"
        assert candidate.reviewed_by_user_id == reviewer
        assert candidate.reviewed_at is not None

    def test_confirm_twice_raises_conflict(self) -> None:
        candidate = IdentityMatchCandidate.create(
            tenant_id=uuid4(),
            party_id=uuid4(),
            candidate_party_id=uuid4(),
            match_score=0.65,
            match_basis={},
        )
        candidate.confirm(uuid4())
        with pytest.raises(ConflictError):
            candidate.confirm(uuid4())

    def test_reject_sets_reason(self) -> None:
        candidate = IdentityMatchCandidate.create(
            tenant_id=uuid4(),
            party_id=uuid4(),
            candidate_party_id=uuid4(),
            match_score=0.65,
            match_basis={},
        )
        candidate.reject(uuid4(), reason="Different borrowers")
        assert candidate.status == "REJECTED"
        assert candidate.reason == "Different borrowers"

    def test_reject_after_confirm_raises_conflict(self) -> None:
        candidate = IdentityMatchCandidate.create(
            tenant_id=uuid4(),
            party_id=uuid4(),
            candidate_party_id=uuid4(),
            match_score=0.65,
            match_basis={},
        )
        candidate.confirm(uuid4())
        with pytest.raises(ConflictError):
            candidate.reject(uuid4())


class TestBorrowerIdentityCreate:
    def test_create_sets_primary_display_name(self) -> None:
        identity = BorrowerIdentity.create(tenant_id=uuid4(), primary_display_name="Jane Doe")
        assert identity.primary_display_name == "Jane Doe"
        assert identity.created_at is not None


class TestBorrowerIdentityMember:
    def test_create_is_active(self) -> None:
        member = BorrowerIdentityMember.create(
            borrower_identity_id=uuid4(),
            party_id=uuid4(),
            application_id=uuid4(),
            linked_by_user_id=uuid4(),
        )
        assert member.is_active is True
        assert member.unlinked_at is None

    def test_unlink_sets_fields(self) -> None:
        member = BorrowerIdentityMember.create(
            borrower_identity_id=uuid4(),
            party_id=uuid4(),
            application_id=uuid4(),
            linked_by_user_id=uuid4(),
        )
        unlinker = uuid4()
        member.unlink(unlinker)
        assert member.is_active is False
        assert member.unlinked_by_user_id == unlinker

    def test_unlink_twice_raises_conflict(self) -> None:
        member = BorrowerIdentityMember.create(
            borrower_identity_id=uuid4(),
            party_id=uuid4(),
            application_id=uuid4(),
            linked_by_user_id=uuid4(),
        )
        member.unlink(uuid4())
        with pytest.raises(ConflictError):
            member.unlink(uuid4())
