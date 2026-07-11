"""Unit tests for mil.compliance.models — DataRetentionPolicy, ConsentRecord."""

from __future__ import annotations

from uuid import uuid4

import pytest

from mil.compliance.models import ConsentRecord, DataRetentionPolicy
from mil.kernel.errors import ValidationError


class TestDataRetentionPolicyCreate:
    def test_create_archive_policy(self) -> None:
        policy = DataRetentionPolicy.create(
            tenant_id=uuid4(), data_category="DOCUMENT", retention_period_days=365, action="ARCHIVE"
        )
        assert policy.action == "ARCHIVE"
        assert policy.retention_period_days == 365

    def test_create_delete_policy_for_non_protected_category(self) -> None:
        policy = DataRetentionPolicy.create(
            tenant_id=uuid4(),
            data_category="NOTIFICATION_LOG",
            retention_period_days=90,
            action="DELETE",
        )
        assert policy.action == "DELETE"

    def test_rejects_delete_for_audit_event(self) -> None:
        with pytest.raises(ValidationError):
            DataRetentionPolicy.create(
                tenant_id=uuid4(),
                data_category="AUDIT_EVENT",
                retention_period_days=90,
                action="DELETE",
            )

    def test_rejects_delete_for_evidence(self) -> None:
        with pytest.raises(ValidationError):
            DataRetentionPolicy.create(
                tenant_id=uuid4(), data_category="EVIDENCE", retention_period_days=90, action="DELETE"
            )

    def test_rejects_invalid_action(self) -> None:
        with pytest.raises(ValidationError):
            DataRetentionPolicy.create(
                tenant_id=uuid4(),
                data_category="DOCUMENT",
                retention_period_days=90,
                action="OBLITERATE",
            )

    def test_rejects_non_positive_retention_period(self) -> None:
        with pytest.raises(ValidationError):
            DataRetentionPolicy.create(
                tenant_id=uuid4(), data_category="DOCUMENT", retention_period_days=0, action="ARCHIVE"
            )


class TestConsentRecordGrant:
    def test_grant_for_party(self) -> None:
        consent = ConsentRecord.grant(
            consent_type="DATA_PROCESSING", consent_text_version="v1", party_id=uuid4()
        )
        assert consent.withdrawn_at is None
        assert consent.party_id is not None
        assert consent.portal_account_id is None

    def test_grant_for_portal_account(self) -> None:
        consent = ConsentRecord.grant(
            consent_type="DATA_PROCESSING", consent_text_version="v1", portal_account_id=uuid4()
        )
        assert consent.portal_account_id is not None
        assert consent.party_id is None

    def test_rejects_both_subjects_set(self) -> None:
        with pytest.raises(ValidationError):
            ConsentRecord.grant(
                consent_type="DATA_PROCESSING",
                consent_text_version="v1",
                party_id=uuid4(),
                portal_account_id=uuid4(),
            )

    def test_rejects_neither_subject_set(self) -> None:
        with pytest.raises(ValidationError):
            ConsentRecord.grant(consent_type="DATA_PROCESSING", consent_text_version="v1")

    def test_rejects_empty_consent_type(self) -> None:
        with pytest.raises(ValidationError):
            ConsentRecord.grant(consent_type="  ", consent_text_version="v1", party_id=uuid4())


class TestConsentRecordWithdraw:
    def test_withdraw_sets_timestamp(self) -> None:
        consent = ConsentRecord.grant(
            consent_type="DATA_PROCESSING", consent_text_version="v1", party_id=uuid4()
        )
        consent.withdraw()
        assert consent.withdrawn_at is not None

    def test_withdraw_twice_is_idempotent(self) -> None:
        consent = ConsentRecord.grant(
            consent_type="DATA_PROCESSING", consent_text_version="v1", party_id=uuid4()
        )
        consent.withdraw()
        first = consent.withdrawn_at
        consent.withdraw()
        assert consent.withdrawn_at == first
