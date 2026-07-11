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

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from mil.policy.models import PolicyPack, PolicyPackApproval, PolicyResult, PolicyRule

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

    def save_result_if_not_exists(self, result: PolicyResult) -> bool:
        """
        Persist an immutable Policy result, treating a uniqueness violation
        as proof a result was already committed for this (finding, policy
        version) by a prior attempt (ADR-008 §5) rather than an error — the
        authoritative fallback beneath ``exists_for_finding_and_version``'s
        read-then-write check, which alone is subject to a race between
        concurrent workers. Isolated with a SAVEPOINT
        (``session.begin_nested``) so a collision here cannot poison the
        caller's per-job Unit of Work.

        Returns:
            ``True`` if this call newly persisted the result, ``False`` if
            one already existed (a replay no-op).
        """
        try:
            with self._session.begin_nested():
                self._session.add(result)
                self._session.flush()
        except IntegrityError:
            return False
        return True

    def get_for_finding(self, finding_id: UUID) -> list[PolicyResult]:
        """Return all Policy results for a Finding, most recent first."""
        stmt = (
            select(PolicyResult)
            .where(PolicyResult.finding_id == finding_id)
            .order_by(PolicyResult.created_at.desc())
        )
        return list(self._session.scalars(stmt))

    def get_by_finding_and_version(
        self, finding_id: UUID, policy_version: str
    ) -> PolicyResult | None:
        """
        Return the Policy result for a Finding under a given policy version,
        or ``None``. Used to recover the pre-existing result when
        ``save_result_if_not_exists`` reports a replay collision — the caller
        (the Policy worker) still needs a real ``PolicyResult`` to dispatch
        the next workflow step.
        """
        stmt = select(PolicyResult).where(
            PolicyResult.finding_id == finding_id,
            PolicyResult.policy_version == policy_version,
        )
        return self._session.scalars(stmt).one_or_none()

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

    def get_results_for_application(self, application_id: UUID) -> list[PolicyResult]:
        """Return all Policy results for an application, most recent first."""
        stmt = (
            select(PolicyResult)
            .where(PolicyResult.application_id == application_id)
            .order_by(PolicyResult.created_at.desc())
        )
        return list(self._session.scalars(stmt))

    def count_by_version_and_outcome(self, tenant_id: UUID) -> list[tuple[str, str, int]]:
        """
        Return ``(policy_version, outcome, count)`` rows for every
        PolicyResult in a tenant (spec 005-enterprise-platform §11, Wave 3 —
        Business Analytics' policy-calibration signal: is a given policy
        version flagging too much or too little). One aggregated query.
        """
        stmt = (
            select(PolicyResult.policy_version, PolicyResult.outcome, func.count(PolicyResult.id))
            .where(PolicyResult.tenant_id == tenant_id)
            .group_by(PolicyResult.policy_version, PolicyResult.outcome)
        )
        return [
            (version, outcome, int(count)) for version, outcome, count in self._session.execute(stmt).all()
        ]

    # ------------------------------------------------------------------
    # PolicyPackApproval (spec 005-enterprise-platform §4)
    # ------------------------------------------------------------------

    def save_approval(self, approval: PolicyPackApproval) -> None:
        self._session.add(approval)
        self._session.flush()

    def get_approval_by_id(self, approval_id: UUID) -> PolicyPackApproval | None:
        return self._session.get(PolicyPackApproval, approval_id)

    def get_pending_approval_for_pack(self, policy_pack_id: UUID) -> PolicyPackApproval | None:
        stmt = select(PolicyPackApproval).where(
            PolicyPackApproval.policy_pack_id == policy_pack_id,
            PolicyPackApproval.decision == "PENDING",
        )
        return self._session.scalars(stmt).one_or_none()

    def get_approved_approval_for_pack(self, policy_pack_id: UUID) -> PolicyPackApproval | None:
        stmt = select(PolicyPackApproval).where(
            PolicyPackApproval.policy_pack_id == policy_pack_id,
            PolicyPackApproval.decision == "APPROVED",
        )
        return self._session.scalars(stmt).one_or_none()

    def get_approvals_for_pack(self, policy_pack_id: UUID) -> list[PolicyPackApproval]:
        stmt = (
            select(PolicyPackApproval)
            .where(PolicyPackApproval.policy_pack_id == policy_pack_id)
            .order_by(PolicyPackApproval.created_at.desc())
        )
        return list(self._session.scalars(stmt))
