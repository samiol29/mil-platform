"""Persistence gateway for the Security & Compliance bounded context."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from mil.compliance.models import ConsentRecord, DataRetentionPolicy

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session


class ComplianceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # DataRetentionPolicy
    # ------------------------------------------------------------------

    def save_policy(self, policy: DataRetentionPolicy) -> None:
        self._session.add(policy)
        self._session.flush()

    def get_policy_for_category(
        self, tenant_id: UUID, data_category: str
    ) -> DataRetentionPolicy | None:
        stmt = select(DataRetentionPolicy).where(
            DataRetentionPolicy.tenant_id == tenant_id,
            DataRetentionPolicy.data_category == data_category,
        )
        return self._session.scalars(stmt).one_or_none()

    def get_policies_for_tenant(self, tenant_id: UUID) -> list[DataRetentionPolicy]:
        stmt = select(DataRetentionPolicy).where(DataRetentionPolicy.tenant_id == tenant_id)
        return list(self._session.scalars(stmt))

    # ------------------------------------------------------------------
    # ConsentRecord
    # ------------------------------------------------------------------

    def save_consent(self, consent: ConsentRecord) -> None:
        self._session.add(consent)
        self._session.flush()

    def get_consents_for_portal_account(self, portal_account_id: UUID) -> list[ConsentRecord]:
        stmt = select(ConsentRecord).where(ConsentRecord.portal_account_id == portal_account_id)
        return list(self._session.scalars(stmt))

    def get_consents_for_party(self, party_id: UUID) -> list[ConsentRecord]:
        stmt = select(ConsentRecord).where(ConsentRecord.party_id == party_id)
        return list(self._session.scalars(stmt))
