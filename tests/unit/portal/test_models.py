"""Unit tests for mil.portal.models — PortalAccount, DocumentChecklistItem."""

from __future__ import annotations

from uuid import uuid4

import pytest

from mil.kernel.errors import AuthenticationError, ConflictError, ValidationError
from mil.portal.models import (
    ACTIVE,
    INVITED,
    RECEIVED,
    WAIVED,
    DocumentChecklistItem,
    PortalAccount,
)


class TestPortalAccountInvite:
    def test_invite_sets_invited_status(self) -> None:
        account, raw_token = PortalAccount.invite(
            tenant_id=uuid4(), party_id=uuid4(), email_hash="abc123"
        )
        assert account.status == INVITED
        assert account.activated_at is None
        assert raw_token != ""
        assert account.invitation_token_hash is not None

    def test_invite_hashes_token_not_stored_raw(self) -> None:
        account, raw_token = PortalAccount.invite(
            tenant_id=uuid4(), party_id=uuid4(), email_hash="abc123"
        )
        assert account.invitation_token_hash != raw_token


class TestPortalAccountActivate:
    def test_activate_with_correct_token(self) -> None:
        account, raw_token = PortalAccount.invite(
            tenant_id=uuid4(), party_id=uuid4(), email_hash="abc123"
        )
        account.activate(raw_token)
        assert account.status == ACTIVE
        assert account.activated_at is not None
        assert account.invitation_token_hash is None

    def test_activate_with_wrong_token_raises(self) -> None:
        account, _raw_token = PortalAccount.invite(
            tenant_id=uuid4(), party_id=uuid4(), email_hash="abc123"
        )
        with pytest.raises(AuthenticationError):
            account.activate("wrong-token")

    def test_activate_twice_raises_conflict(self) -> None:
        account, raw_token = PortalAccount.invite(
            tenant_id=uuid4(), party_id=uuid4(), email_hash="abc123"
        )
        account.activate(raw_token)
        with pytest.raises(ConflictError):
            account.activate(raw_token)


class TestPortalAccountSuspend:
    def test_suspend_sets_status(self) -> None:
        account, raw_token = PortalAccount.invite(
            tenant_id=uuid4(), party_id=uuid4(), email_hash="abc123"
        )
        account.activate(raw_token)
        account.suspend()
        assert account.status == "SUSPENDED"


class TestDocumentChecklistItemCreate:
    def test_create_sets_requested_status(self) -> None:
        item = DocumentChecklistItem.create(
            tenant_id=uuid4(),
            application_id=uuid4(),
            label="Latest bank statement",
            document_type="BANK_STATEMENT",
            requested_by_user_id=uuid4(),
        )
        assert item.status == "REQUESTED"
        assert item.party_id is None

    def test_create_rejects_empty_label(self) -> None:
        with pytest.raises(ValidationError):
            DocumentChecklistItem.create(
                tenant_id=uuid4(),
                application_id=uuid4(),
                label="  ",
                document_type="BANK_STATEMENT",
                requested_by_user_id=uuid4(),
            )


class TestDocumentChecklistItemFulfill:
    def test_fulfill_sets_received(self) -> None:
        item = DocumentChecklistItem.create(
            tenant_id=uuid4(),
            application_id=uuid4(),
            label="Bank statement",
            document_type="BANK_STATEMENT",
            requested_by_user_id=uuid4(),
        )
        doc_id = uuid4()
        item.fulfill(doc_id)
        assert item.status == RECEIVED
        assert item.fulfilled_document_id == doc_id

    def test_fulfill_twice_raises_conflict(self) -> None:
        item = DocumentChecklistItem.create(
            tenant_id=uuid4(),
            application_id=uuid4(),
            label="Bank statement",
            document_type="BANK_STATEMENT",
            requested_by_user_id=uuid4(),
        )
        item.fulfill(uuid4())
        with pytest.raises(ConflictError):
            item.fulfill(uuid4())


class TestDocumentChecklistItemWaive:
    def test_waive_sets_waived(self) -> None:
        item = DocumentChecklistItem.create(
            tenant_id=uuid4(),
            application_id=uuid4(),
            label="Bank statement",
            document_type="BANK_STATEMENT",
            requested_by_user_id=uuid4(),
        )
        item.waive()
        assert item.status == WAIVED

    def test_waive_after_fulfill_raises_conflict(self) -> None:
        item = DocumentChecklistItem.create(
            tenant_id=uuid4(),
            application_id=uuid4(),
            label="Bank statement",
            document_type="BANK_STATEMENT",
            requested_by_user_id=uuid4(),
        )
        item.fulfill(uuid4())
        with pytest.raises(ConflictError):
            item.waive()
