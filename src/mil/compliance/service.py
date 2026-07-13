"""
ComplianceService — use-case orchestrator for the Security & Compliance
bounded context (spec 005-enterprise-platform §16, Wave 4).

Mirrors ``mil.borrower_identity.service``'s pattern: internal-staff methods
self-check RBAC (``Permission.MANAGE_COMPLIANCE``/``READ_COMPLIANCE``);
``record_consent`` is a portal-safe primitive (no internal RBAC — called by
the Customer Portal composition layer at account activation, §12).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mil.compliance.models import ConsentRecord, DataRetentionPolicy
from mil.kernel.security import Permission, require_permission

if TYPE_CHECKING:
    from uuid import UUID

    from mil.audit.writer import AuditWriter
    from mil.compliance.repository import ComplianceRepository
    from mil.kernel.security import AuthenticatedUser


class ComplianceService:
    def __init__(self, repository: ComplianceRepository, audit: AuditWriter) -> None:
        self._repo = repository
        self._audit = audit

    # ------------------------------------------------------------------
    # Internal-staff methods (self-checking internal RBAC)
    # ------------------------------------------------------------------

    def set_retention_policy(
        self,
        caller: AuthenticatedUser,
        *,
        tenant_id: UUID,
        data_category: str,
        retention_period_days: int,
        action: str,
    ) -> DataRetentionPolicy:
        require_permission(caller, Permission.MANAGE_COMPLIANCE)
        existing = self._repo.get_policy_for_category(tenant_id, data_category)
        # Validate via the factory (rejects DELETE for AUDIT_EVENT/EVIDENCE,
        # bad action values, non-positive periods) before mutating anything.
        validated = DataRetentionPolicy.create(
            tenant_id=tenant_id,
            data_category=data_category,
            retention_period_days=retention_period_days,
            action=action,
        )
        if existing is not None:
            existing.retention_period_days = validated.retention_period_days
            existing.action = validated.action
            policy = existing
        else:
            policy = validated
        self._repo.save_policy(policy)
        self._audit.record(
            event_type="RETENTION_POLICY_SET",
            entity_type="DATA_RETENTION_POLICY",
            entity_id=policy.id,
            tenant_id=tenant_id,
            actor_id=caller.user_id,
            event_data={
                "data_category": data_category,
                "retention_period_days": retention_period_days,
                "action": action,
            },
        )
        return policy

    def get_retention_policies(
        self, caller: AuthenticatedUser, tenant_id: UUID
    ) -> list[DataRetentionPolicy]:
        require_permission(caller, Permission.READ_COMPLIANCE)
        return self._repo.get_policies_for_tenant(tenant_id)

    # ------------------------------------------------------------------
    # Portal-safe primitive (no internal RBAC — see module docstring)
    # ------------------------------------------------------------------

    def record_consent(
        self,
        *,
        tenant_id: UUID,
        consent_type: str,
        consent_text_version: str,
        party_id: UUID | None = None,
        portal_account_id: UUID | None = None,
    ) -> ConsentRecord:
        """
        ``tenant_id`` is used only for the audit event — ``ConsentRecord``
        itself has no ``tenant_id`` column (per spec §16.5, scoped by
        ``partyId``/``portalAccountId`` alone).
        """
        consent = ConsentRecord.grant(
            consent_type=consent_type,
            consent_text_version=consent_text_version,
            party_id=party_id,
            portal_account_id=portal_account_id,
        )
        self._repo.save_consent(consent)
        self._audit.record(
            event_type="CONSENT_GRANTED",
            entity_type="CONSENT_RECORD",
            entity_id=consent.id,
            tenant_id=tenant_id,
            event_data={"consent_type": consent_type, "consent_text_version": consent_text_version},
        )
        return consent
