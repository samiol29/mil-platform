"""Persistence gateway for the Borrower Identity Resolution bounded context."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from mil.borrower_identity.models import (
    BorrowerIdentity,
    BorrowerIdentityMember,
    IdentityMatchCandidate,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session


class BorrowerIdentityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # IdentityMatchCandidate
    # ------------------------------------------------------------------

    def save_candidate(self, candidate: IdentityMatchCandidate) -> None:
        self._session.add(candidate)
        self._session.flush()

    def get_candidate_by_id(self, candidate_id: UUID) -> IdentityMatchCandidate | None:
        return self._session.get(IdentityMatchCandidate, candidate_id)

    def get_candidates_for_party(self, party_id: UUID) -> list[IdentityMatchCandidate]:
        stmt = (
            select(IdentityMatchCandidate)
            .where(IdentityMatchCandidate.party_id == party_id)
            .order_by(IdentityMatchCandidate.created_at.desc())
        )
        return list(self._session.scalars(stmt))

    def get_pending_candidate(
        self, party_id: UUID, candidate_party_id: UUID
    ) -> IdentityMatchCandidate | None:
        stmt = select(IdentityMatchCandidate).where(
            IdentityMatchCandidate.party_id == party_id,
            IdentityMatchCandidate.candidate_party_id == candidate_party_id,
            IdentityMatchCandidate.status == "PENDING",
        )
        return self._session.scalars(stmt).one_or_none()

    # ------------------------------------------------------------------
    # BorrowerIdentity / BorrowerIdentityMember
    # ------------------------------------------------------------------

    def save_identity(self, identity: BorrowerIdentity) -> None:
        self._session.add(identity)
        self._session.flush()

    def get_identity_by_id(self, identity_id: UUID) -> BorrowerIdentity | None:
        return self._session.get(BorrowerIdentity, identity_id)

    def save_member(self, member: BorrowerIdentityMember) -> None:
        self._session.add(member)
        self._session.flush()

    def get_active_member_for_party(self, party_id: UUID) -> BorrowerIdentityMember | None:
        stmt = select(BorrowerIdentityMember).where(
            BorrowerIdentityMember.party_id == party_id,
            BorrowerIdentityMember.unlinked_at.is_(None),
        )
        return self._session.scalars(stmt).one_or_none()

    def get_active_members_for_identity(self, identity_id: UUID) -> list[BorrowerIdentityMember]:
        stmt = select(BorrowerIdentityMember).where(
            BorrowerIdentityMember.borrower_identity_id == identity_id,
            BorrowerIdentityMember.unlinked_at.is_(None),
        )
        return list(self._session.scalars(stmt))
