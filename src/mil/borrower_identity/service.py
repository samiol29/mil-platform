"""
BorrowerIdentityService — use-case orchestrator for the Borrower Identity
Resolution bounded context (spec 005-enterprise-platform §5, Wave 3).

Matching is deliberately conservative and fully explainable (Principle III):

- **Deterministic**: an exact match on a real, already-stored hashed
  external identifier (``Party.external_identifier_hash`` +
  ``identifier_type``) — score 0.98.
- **Probabilistic**: an exact match on *normalized* ``display_name`` (case/
  whitespace/punctuation-insensitive) — the only other real signal MIL
  stores about a party — score 0.65.

No DOB/address/phone/email matching: MIL does not store those fields
(confirmed against ``mil.application.models.Party`` before this module was
written — Principle V, least-data). A candidate with no real signal is
never created with a guessed score.

Every match is advisory (``IdentityMatchCandidate``, status PENDING) until a
human confirms or rejects it (Principle I) — ``confirm_match`` is the only
path that creates/extends a ``BorrowerIdentity``.

Dependency rule: imports only from ``mil.borrower_identity``, ``mil.kernel``,
and the Python standard library. The caller (API route composition) supplies
``PartyMatchInput`` for the subject and candidate pool — this service never
imports ``mil.application``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mil.borrower_identity.models import BorrowerIdentity, BorrowerIdentityMember, IdentityMatchCandidate
from mil.kernel.errors import NotFoundError
from mil.kernel.security import Permission, require_permission

if TYPE_CHECKING:
    from uuid import UUID

    from mil.audit.writer import AuditWriter
    from mil.borrower_identity.repository import BorrowerIdentityRepository
    from mil.kernel.security import AuthenticatedUser

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCTUATION_RE = re.compile(r"[^\w\s]")


@dataclass(frozen=True)
class PartyMatchInput:
    """A minimal, domain-agnostic view of a Party for matching (no PII beyond display_name)."""

    party_id: UUID
    application_id: UUID
    display_name: str
    external_identifier_hash: str | None = None
    identifier_type: str | None = None


def _normalize_name(name: str) -> str:
    lowered = name.strip().lower()
    no_punctuation = _PUNCTUATION_RE.sub("", lowered)
    return _WHITESPACE_RE.sub(" ", no_punctuation).strip()


class BorrowerIdentityService:
    def __init__(self, repository: BorrowerIdentityRepository, audit: AuditWriter) -> None:
        self._repo = repository
        self._audit = audit

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def compute_candidates(
        self,
        caller: AuthenticatedUser,
        *,
        tenant_id: UUID,
        subject: PartyMatchInput,
        others: list[PartyMatchInput],
    ) -> list[IdentityMatchCandidate]:
        """
        Compute and persist match candidates between ``subject`` and every
        party in ``others`` belonging to a *different* application.

        Idempotent in spirit: skips any pair that already has a PENDING
        candidate rather than creating a duplicate suggestion.
        """
        require_permission(caller, Permission.CONFIRM_IDENTITY_MATCH)
        created: list[IdentityMatchCandidate] = []
        subject_name = _normalize_name(subject.display_name)

        for other in others:
            if other.party_id == subject.party_id:
                continue
            if other.application_id == subject.application_id:
                continue
            if self._repo.get_pending_candidate(subject.party_id, other.party_id) is not None:
                continue

            score: float | None = None
            basis: dict[str, object] = {}

            if (
                subject.external_identifier_hash is not None
                and other.external_identifier_hash is not None
                and subject.identifier_type == other.identifier_type
                and subject.external_identifier_hash == other.external_identifier_hash
            ):
                score = 0.98
                basis = {
                    "exact_identifier_match": True,
                    "identifier_type": subject.identifier_type,
                }
            elif subject_name != "" and subject_name == _normalize_name(other.display_name):
                score = 0.65
                basis = {"name_similarity": "exact_normalized_match"}

            if score is None:
                continue

            candidate = IdentityMatchCandidate.create(
                tenant_id=tenant_id,
                party_id=subject.party_id,
                candidate_party_id=other.party_id,
                match_score=score,
                match_basis=basis,
            )
            self._repo.save_candidate(candidate)
            created.append(candidate)

        return created

    def get_candidates_for_party(
        self, caller: AuthenticatedUser, party_id: UUID
    ) -> list[IdentityMatchCandidate]:
        require_permission(caller, Permission.READ_CROSS_APPLICATION_IDENTITY)
        return self._repo.get_candidates_for_party(party_id)

    # ------------------------------------------------------------------
    # Confirm / reject
    # ------------------------------------------------------------------

    def confirm_match(
        self, caller: AuthenticatedUser, candidate: IdentityMatchCandidate
    ) -> BorrowerIdentity:
        """
        Confirm a match, creating a ``BorrowerIdentity`` on first
        confirmation for either party, or linking into an existing one.
        """
        require_permission(caller, Permission.CONFIRM_IDENTITY_MATCH)
        candidate.confirm(caller.user_id)
        self._repo.save_candidate(candidate)

        existing = self._repo.get_active_member_for_party(
            candidate.party_id
        ) or self._repo.get_active_member_for_party(candidate.candidate_party_id)

        if existing is not None:
            identity = self._repo.get_identity_by_id(existing.borrower_identity_id)
            if identity is None:
                raise NotFoundError("BorrowerIdentity", existing.borrower_identity_id)
        else:
            identity = BorrowerIdentity.create(
                tenant_id=candidate.tenant_id, primary_display_name=""
            )
            self._repo.save_identity(identity)

        self._audit.record(
            event_type="IDENTITY_MATCH_CONFIRMED",
            entity_type="IDENTITY_MATCH_CANDIDATE",
            entity_id=candidate.id,
            tenant_id=candidate.tenant_id,
            actor_id=caller.user_id,
            event_data={
                "party_id": str(candidate.party_id),
                "candidate_party_id": str(candidate.candidate_party_id),
                "borrower_identity_id": str(identity.id),
            },
        )
        return identity

    def reject_match(
        self,
        caller: AuthenticatedUser,
        candidate: IdentityMatchCandidate,
        reason: str | None = None,
    ) -> IdentityMatchCandidate:
        require_permission(caller, Permission.CONFIRM_IDENTITY_MATCH)
        candidate.reject(caller.user_id, reason)
        self._repo.save_candidate(candidate)
        self._audit.record(
            event_type="IDENTITY_MATCH_REJECTED",
            entity_type="IDENTITY_MATCH_CANDIDATE",
            entity_id=candidate.id,
            tenant_id=candidate.tenant_id,
            actor_id=caller.user_id,
            event_data={"reason": reason},
        )
        return candidate

    def get_candidate(
        self, caller: AuthenticatedUser, candidate_id: UUID
    ) -> IdentityMatchCandidate:
        require_permission(caller, Permission.CONFIRM_IDENTITY_MATCH)
        candidate = self._repo.get_candidate_by_id(candidate_id)
        if candidate is None or candidate.tenant_id != caller.tenant_id:
            raise NotFoundError("IdentityMatchCandidate", candidate_id)
        return candidate

    def link_member(
        self,
        caller: AuthenticatedUser,
        *,
        identity: BorrowerIdentity,
        party_id: UUID,
        application_id: UUID,
    ) -> BorrowerIdentityMember:
        """Link a party/application into a confirmed BorrowerIdentity, if not already linked."""
        existing = self._repo.get_active_member_for_party(party_id)
        if existing is not None:
            return existing
        member = BorrowerIdentityMember.create(
            borrower_identity_id=identity.id,
            party_id=party_id,
            application_id=application_id,
            linked_by_user_id=caller.user_id,
        )
        self._repo.save_member(member)
        return member

    def get_identity(self, caller: AuthenticatedUser, identity_id: UUID) -> BorrowerIdentity:
        require_permission(caller, Permission.READ_CROSS_APPLICATION_IDENTITY)
        identity = self._repo.get_identity_by_id(identity_id)
        if identity is None or identity.tenant_id != caller.tenant_id:
            raise NotFoundError("BorrowerIdentity", identity_id)
        return identity

    def get_members(
        self, caller: AuthenticatedUser, identity_id: UUID
    ) -> list[BorrowerIdentityMember]:
        require_permission(caller, Permission.READ_CROSS_APPLICATION_IDENTITY)
        return self._repo.get_active_members_for_identity(identity_id)

    def get_identity_for_party(
        self, caller: AuthenticatedUser, party_id: UUID
    ) -> BorrowerIdentity | None:
        require_permission(caller, Permission.READ_CROSS_APPLICATION_IDENTITY)
        member = self._repo.get_active_member_for_party(party_id)
        if member is None:
            return None
        return self._repo.get_identity_by_id(member.borrower_identity_id)
