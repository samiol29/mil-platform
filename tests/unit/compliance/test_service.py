"""Unit tests for mil.compliance.service — ComplianceService."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from mil.compliance.service import ComplianceService
from mil.kernel.errors import AuthorizationError, ValidationError
from mil.kernel.security import AuthenticatedUser, Role

if TYPE_CHECKING:
    from mil.compliance.models import ConsentRecord, DataRetentionPolicy


class FakeComplianceRepository:
    def __init__(self) -> None:
        self.policies: dict[object, DataRetentionPolicy] = {}
        self.consents: list[ConsentRecord] = []

    def save_policy(self, policy: DataRetentionPolicy) -> None:
        self.policies[policy.id] = policy

    def get_policy_for_category(self, tenant_id: object, data_category: str):
        for p in self.policies.values():
            if p.tenant_id == tenant_id and p.data_category == data_category:
                return p
        return None

    def get_policies_for_tenant(self, tenant_id: object) -> list[DataRetentionPolicy]:
        return [p for p in self.policies.values() if p.tenant_id == tenant_id]

    def save_consent(self, consent: ConsentRecord) -> None:
        self.consents.append(consent)

    def get_consents_for_portal_account(self, portal_account_id: object):
        return [c for c in self.consents if c.portal_account_id == portal_account_id]

    def get_consents_for_party(self, party_id: object):
        return [c for c in self.consents if c.party_id == party_id]


class FakeAuditWriter:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record(self, **kwargs: object) -> object:
        self.records.append(kwargs)
        return object()


def _make_service() -> tuple[ComplianceService, FakeComplianceRepository, FakeAuditWriter]:
    repo = FakeComplianceRepository()
    audit = FakeAuditWriter()
    return ComplianceService(repo, audit), repo, audit  # type: ignore[arg-type]


def _compliance_officer(tenant_id: object) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(), tenant_id=tenant_id, roles=frozenset({Role.COMPLIANCE_OFFICER})
    )


def _readonly_caller(tenant_id: object) -> AuthenticatedUser:
    return AuthenticatedUser(user_id=uuid4(), tenant_id=tenant_id, roles=frozenset({Role.CREDIT_ANALYST}))


class TestSetRetentionPolicy:
    def test_creates_new_policy(self) -> None:
        service, repo, audit = _make_service()
        tenant_id = uuid4()
        caller = _compliance_officer(tenant_id)

        policy = service.set_retention_policy(
            caller,
            tenant_id=tenant_id,
            data_category="DOCUMENT",
            retention_period_days=365,
            action="ARCHIVE",
        )
        assert policy.retention_period_days == 365
        assert audit.records[-1]["event_type"] == "RETENTION_POLICY_SET"
        assert len(repo.policies) == 1

    def test_updates_existing_policy_in_place(self) -> None:
        service, repo, _audit = _make_service()
        tenant_id = uuid4()
        caller = _compliance_officer(tenant_id)

        first = service.set_retention_policy(
            caller, tenant_id=tenant_id, data_category="DOCUMENT", retention_period_days=365, action="ARCHIVE"
        )
        second = service.set_retention_policy(
            caller, tenant_id=tenant_id, data_category="DOCUMENT", retention_period_days=730, action="ARCHIVE"
        )
        assert second.id == first.id
        assert second.retention_period_days == 730
        assert len(repo.policies) == 1

    def test_rejects_delete_for_audit_event(self) -> None:
        service, _repo, _audit = _make_service()
        tenant_id = uuid4()
        caller = _compliance_officer(tenant_id)
        with pytest.raises(ValidationError):
            service.set_retention_policy(
                caller,
                tenant_id=tenant_id,
                data_category="AUDIT_EVENT",
                retention_period_days=90,
                action="DELETE",
            )

    def test_readonly_role_forbidden(self) -> None:
        service, _repo, _audit = _make_service()
        caller = _readonly_caller(uuid4())
        with pytest.raises(AuthorizationError):
            service.set_retention_policy(
                caller,
                tenant_id=uuid4(),
                data_category="DOCUMENT",
                retention_period_days=90,
                action="ARCHIVE",
            )


class TestGetRetentionPolicies:
    def test_readonly_role_forbidden(self) -> None:
        service, _repo, _audit = _make_service()
        caller = _readonly_caller(uuid4())
        with pytest.raises(AuthorizationError):
            service.get_retention_policies(caller, uuid4())


class TestRecordConsent:
    def test_records_consent_no_rbac_required(self) -> None:
        service, repo, audit = _make_service()
        consent = service.record_consent(
            tenant_id=uuid4(),
            consent_type="PORTAL_TOS",
            consent_text_version="v1",
            portal_account_id=uuid4(),
        )
        assert consent in repo.consents
        assert audit.records[-1]["event_type"] == "CONSENT_GRANTED"
