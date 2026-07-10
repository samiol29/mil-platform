"""
PolicyService — use-case orchestrator for the Policy bounded context.

Two responsibilities:

1. **Policy Pack / Rule lifecycle** (administrative use case): create a pack,
   activate/deactivate it (enforcing at most one active pack per tenant),
   and register its rule catalogue. ``mil.policy`` never hardcodes
   verification logic here — rules are catalogue data; the actual
   triggering condition lives in the registered ``PolicyProvider``.

2. **Policy result persistence** (the Policy worker's use case): record an
   immutable ``PolicyResult`` from a provider's ``PolicyEvaluationResult``
   and emit the ``POLICY_EVALUATED`` audit event, synchronously, in the same
   database transaction (audit is never routed through the outbox).

Explainability/attribution enforcement happens in ``PolicyResult.create``
itself — an incomplete result raises ``PolicyEvaluationError`` before a row
can ever be constructed, so this service does not duplicate that check.

``PolicyService`` never performs human review and has no knowledge of
Copilot.

Dependency rule: imports only from ``mil.policy``, ``mil.kernel``, and the
Python standard library. No other bounded context is imported.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mil.kernel.errors import ConflictError
from mil.policy.models import PolicyPack, PolicyResult, PolicyRule

if TYPE_CHECKING:
    from uuid import UUID

    from mil.audit.writer import AuditWriter
    from mil.kernel.providers.policy import PolicyEvaluationResult
    from mil.policy.repository import PolicyRepository


class PolicyService:
    """
    Orchestrates Policy Pack lifecycle and Policy result creation.

    Construct per unit of work with a repository and audit writer bound to
    the active session, so that every write and its audit event commit in
    the same transaction as the caller's other writes.
    """

    def __init__(self, repository: PolicyRepository, audit: AuditWriter) -> None:
        self._repo = repository
        self._audit = audit

    # ------------------------------------------------------------------
    # Policy Pack lifecycle
    # ------------------------------------------------------------------

    def create_pack(
        self,
        *,
        tenant_id: UUID,
        version: str,
        name: str,
        content_hash: str,
        jurisdiction: str | None = None,
        created_by: UUID | None = None,
    ) -> PolicyPack:
        """Create a new, inactive Policy Pack and record ``POLICY_PACK_CREATED``."""
        pack = PolicyPack.create(
            tenant_id=tenant_id,
            version=version,
            name=name,
            content_hash=content_hash,
            jurisdiction=jurisdiction,
            created_by=created_by,
        )
        self._repo.save_pack(pack)
        self._audit.record(
            event_type="POLICY_PACK_CREATED",
            entity_type="POLICY_PACK",
            entity_id=pack.id,
            tenant_id=tenant_id,
            actor_id=created_by,
            event_data={"version": pack.version, "name": pack.name},
        )
        return pack

    def activate_pack(self, pack: PolicyPack) -> PolicyPack:
        """
        Activate a Policy Pack, enforcing at most one active pack per tenant.

        Raises:
            ConflictError: If another pack is already active for this tenant,
                or if ``pack`` itself cannot be activated (``PolicyPack.activate``).
        """
        existing_active = self._repo.get_active_pack_for_tenant(pack.tenant_id)
        if existing_active is not None and existing_active.id != pack.id:
            raise ConflictError(
                f"Tenant {pack.tenant_id} already has an active Policy Pack "
                f"({existing_active.id}); deactivate it first"
            )
        pack.activate()
        self._repo.save_pack(pack)
        self._audit.record(
            event_type="POLICY_PACK_ACTIVATED",
            entity_type="POLICY_PACK",
            entity_id=pack.id,
            tenant_id=pack.tenant_id,
            event_data={"version": pack.version},
        )
        return pack

    def deactivate_pack(self, pack: PolicyPack) -> PolicyPack:
        """Deactivate a Policy Pack and record ``POLICY_PACK_DEACTIVATED``."""
        pack.deactivate()
        self._repo.save_pack(pack)
        self._audit.record(
            event_type="POLICY_PACK_DEACTIVATED",
            entity_type="POLICY_PACK",
            entity_id=pack.id,
            tenant_id=pack.tenant_id,
            event_data={"version": pack.version},
        )
        return pack

    def add_rule(
        self,
        *,
        policy_pack_id: UUID,
        tenant_id: UUID,
        rule_key: str,
        name: str,
        description: str,
        severity: str,
    ) -> PolicyRule:
        """Add a rule to a Policy Pack's catalogue and record ``POLICY_RULE_ADDED``."""
        rule = PolicyRule.create(
            policy_pack_id=policy_pack_id,
            rule_key=rule_key,
            name=name,
            description=description,
            severity=severity,
        )
        self._repo.save_rule(rule)
        self._audit.record(
            event_type="POLICY_RULE_ADDED",
            entity_type="POLICY_RULE",
            entity_id=rule.id,
            tenant_id=tenant_id,
            event_data={"policy_pack_id": str(policy_pack_id), "rule_key": rule.rule_key},
        )
        return rule

    # ------------------------------------------------------------------
    # Policy result persistence (the Policy worker's use case)
    # ------------------------------------------------------------------

    def record_policy_result(
        self,
        *,
        finding_id: UUID,
        application_id: UUID,
        tenant_id: UUID,
        workflow_run_id: UUID,
        policy_pack_id: UUID,
        result: PolicyEvaluationResult,
    ) -> tuple[PolicyResult, bool]:
        """
        Create one immutable ``PolicyResult`` from a provider evaluation and
        emit a ``POLICY_EVALUATED`` audit event.

        Idempotent replay (ADR-008 §5): if a result already exists for this
        (finding, policy version) — the race the caller's own up-front
        ``exists_for_finding_and_version`` check cannot fully close under
        concurrent workers — that pre-existing result is returned instead of
        raising, paired with ``False``. The caller still needs a real
        ``PolicyResult`` (to dispatch the next workflow step) but must not
        publish a duplicate audit event.

        Returns:
            A ``(policy_result, created)`` pair: ``created`` is ``True`` only
            when this call newly persisted the result.

        Raises:
            PolicyEvaluationError: If ``result`` is missing required
                attribution (raised by ``PolicyResult.create``).
        """
        policy_result = PolicyResult.create(
            finding_id=finding_id,
            application_id=application_id,
            tenant_id=tenant_id,
            workflow_run_id=workflow_run_id,
            policy_pack_id=policy_pack_id,
            result=result,
        )
        if not self._repo.save_result_if_not_exists(policy_result):
            existing = self._repo.get_by_finding_and_version(
                finding_id, policy_result.policy_version
            )
            if existing is None:
                raise ConflictError(
                    f"Policy result for finding {finding_id} at version "
                    f"{policy_result.policy_version} could not be recovered after a "
                    "uniqueness conflict."
                )
            return existing, False
        self._audit.record(
            event_type="POLICY_EVALUATED",
            entity_type="POLICY_RESULT",
            entity_id=policy_result.id,
            tenant_id=tenant_id,
            application_id=application_id,
            event_data={
                "finding_id": str(finding_id),
                "policy_pack_id": str(policy_pack_id),
                "policy_version": policy_result.policy_version,
                "outcome": policy_result.outcome,
                "triggered_rule_keys": policy_result.triggered_rule_keys,
            },
        )
        return policy_result, True
