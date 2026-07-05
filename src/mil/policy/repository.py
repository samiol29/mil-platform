"""
Persistence gateway for the Policy bounded context.

``PolicyRepository`` covers all three Policy entities:

- ``PolicyPack`` / ``PolicyRule`` — regular CRUD (mutable lifecycle metadata
  for packs; static catalogue rows for rules).
- ``PolicyResult`` — append-only: writes immutable rows and never updates or
  deletes them. Does not commit — the caller (the Policy worker's per-job
  Unit of Work, or the admin service call) owns the transaction.

Idempotency (ADR-008): ``exists_for_finding_and_version`` lets the Policy
worker detect a replay (a result already exists for this Finding under this
policy version) and treat it as a no-op rather than re-evaluating; the unique
constraint on ``(finding_id, policy_version)`` is the backing authority.

Dependency rule: imports only from ``mil.policy.models``, ``mil.kernel``, and
the Python standard library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from mil.policy.models import PolicyPack, PolicyResult, PolicyRule

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session


class PolicyRepository:
    """Persistence gateway for ``PolicyPack``, ``PolicyRule``, and ``PolicyResult`` rows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # PolicyPack
    # ------------------------------------------------------------------

    def save_pack(self, pack: PolicyPack) -> None:
        """Persist a Policy Pack (create or update). Adds and flushes."""
        self._session.add(pack)
        self._session.flush()

    def get_pack_by_id(self, pack_id: UUID) -> PolicyPack | None:
        """Return the Policy Pack with the given id, or ``None``."""
        return self._session.get(PolicyPack, pack_id)

    def get_active_pack_for_tenant(self, tenant_id: UUID) -> PolicyPack | None:
        """
        Return the tenant's currently active Policy Pack, or ``None`` if none
        is active.
        """
        stmt = select(PolicyPack).where(
            PolicyPack.tenant_id == tenant_id,
            PolicyPack.activated_at.is_not(None),
            PolicyPack.deactivated_at.is_(None),
        )
        return self._session.scalars(stmt).one_or_none()

    def get_packs_for_tenant(self, tenant_id: UUID) -> list[PolicyPack]:
        """Return all Policy Packs for a tenant, most recent first."""
        stmt = (
            select(PolicyPack)
            .where(PolicyPack.tenant_id == tenant_id)
            .order_by(PolicyPack.created_at.desc())
        )
        return list(self._session.scalars(stmt))

    # ------------------------------------------------------------------
    # PolicyRule
    # ------------------------------------------------------------------

    def save_rule(self, rule: PolicyRule) -> None:
        """Persist a Policy Rule. Adds and flushes."""
        self._session.add(rule)
        self._session.flush()

    def get_rules_for_pack(self, policy_pack_id: UUID) -> list[PolicyRule]:
        """Return every rule belonging to a Policy Pack."""
        stmt = select(PolicyRule).where(PolicyRule.policy_pack_id == policy_pack_id)
        return list(self._session.scalars(stmt))

    # ------------------------------------------------------------------
    # PolicyResult (append-only)
    # ------------------------------------------------------------------

    def save_result(self, result: PolicyResult) -> None:
        """
        Persist an immutable Policy result.

        Adds the result and flushes so a uniqueness violation (duplicate
        finding + policy version) surfaces within the caller's transaction.
        """
        self._session.add(result)
        self._session.flush()

    def get_for_finding(self, finding_id: UUID) -> list[PolicyResult]:
        """Return all Policy results for a Finding, most recent first."""
        stmt = (
            select(PolicyResult)
            .where(PolicyResult.finding_id == finding_id)
            .order_by(PolicyResult.created_at.desc())
        )
        return list(self._session.scalars(stmt))

    def exists_for_finding_and_version(self, finding_id: UUID, policy_version: str) -> bool:
        """
        Return ``True`` if a Policy result already exists for a Finding under
        a given policy version.

        This is the job-level idempotency check (ADR-008): a non-``False``
        result means this Finding has already been evaluated
        deterministically under this policy version, within the same
        all-or-nothing per-job transaction.
        """
        stmt = select(PolicyResult.id).where(
            PolicyResult.finding_id == finding_id,
            PolicyResult.policy_version == policy_version,
        )
        return self._session.scalars(stmt).first() is not None
