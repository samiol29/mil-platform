"""Unit tests for mil.portal.service — PortalService."""

from __future__ import annotations

from uuid import uuid4

import pytest

from mil.kernel.errors import AuthorizationError
from mil.kernel.security import AuthenticatedUser, Role
from mil.portal.models import DocumentChecklistItem, PortalAccount
from mil.portal.service import PortalService


class FakePortalRepository:
    def __init__(self) -> None:
        self.accounts: dict[object, PortalAccount] = {}
        self.items: dict[object, DocumentChecklistItem] = {}

    def save_account(self, account: PortalAccount) -> None:
        self.accounts[account.id] = account

    def get_account_by_id(self, account_id: object) -> PortalAccount | None:
        return self.accounts.get(account_id)

    def get_account_for_party(self, party_id: object) -> PortalAccount | None:
        for a in self.accounts.values():
            if a.party_id == party_id:
                return a
        return None

    def save_item(self, item: DocumentChecklistItem) -> None:
        self.items[item.id] = item

    def get_item_by_id(self, item_id: object) -> DocumentChecklistItem | None:
        return self.items.get(item_id)

    def get_items_for_application(self, application_id: object) -> list[DocumentChecklistItem]:
        return [i for i in self.items.values() if i.application_id == application_id]


class FakeAuditWriter:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record(self, **kwargs: object) -> object:
        self.records.append(kwargs)
        return object()


def _make_service() -> tuple[PortalService, FakePortalRepository, FakeAuditWriter]:
    repo = FakePortalRepository()
    audit = FakeAuditWriter()
    return PortalService(repo, audit), repo, audit  # type: ignore[arg-type]


def _rm_caller(tenant_id: object) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(), tenant_id=tenant_id, roles=frozenset({Role.RELATIONSHIP_MANAGER})
    )


def _readonly_caller(tenant_id: object) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(), tenant_id=tenant_id, roles=frozenset({Role.AUDIT_TEAM})
    )


class TestCreateChecklistItem:
    def test_creates_item(self) -> None:
        service, repo, audit = _make_service()
        tenant_id = uuid4()
        caller = _rm_caller(tenant_id)
        app_id = uuid4()

        item = service.create_checklist_item(
            caller,
            tenant_id=tenant_id,
            application_id=app_id,
            label="Bank statement",
            document_type="BANK_STATEMENT",
        )
        assert item.status == "REQUESTED"
        assert audit.records[-1]["event_type"] == "CHECKLIST_ITEM_REQUESTED"
        assert app_id in {i.application_id for i in repo.items.values()}

    def test_readonly_role_forbidden(self) -> None:
        service, _, _ = _make_service()
        caller = _readonly_caller(uuid4())
        with pytest.raises(AuthorizationError):
            service.create_checklist_item(
                caller,
                tenant_id=uuid4(),
                application_id=uuid4(),
                label="Bank statement",
                document_type="BANK_STATEMENT",
            )


class TestInviteBorrower:
    def test_creates_account_and_returns_raw_token(self) -> None:
        service, repo, audit = _make_service()
        tenant_id = uuid4()
        caller = _rm_caller(tenant_id)
        party_id = uuid4()

        account, raw_token = service.invite_borrower(
            caller, tenant_id=tenant_id, party_id=party_id, email_hash="hash123"
        )
        assert account.status == "INVITED"
        assert raw_token != ""
        assert audit.records[-1]["event_type"] == "PORTAL_ACCOUNT_INVITED"
        assert repo.get_account_for_party(party_id) is account

    def test_reinviting_returns_existing_account_with_empty_token(self) -> None:
        service, _repo, _audit = _make_service()
        tenant_id = uuid4()
        caller = _rm_caller(tenant_id)
        party_id = uuid4()

        first, _ = service.invite_borrower(
            caller, tenant_id=tenant_id, party_id=party_id, email_hash="hash123"
        )
        second, raw_token = service.invite_borrower(
            caller, tenant_id=tenant_id, party_id=party_id, email_hash="hash123"
        )
        assert second.id == first.id
        assert raw_token == ""

    def test_readonly_role_forbidden(self) -> None:
        service, _, _ = _make_service()
        caller = _readonly_caller(uuid4())
        with pytest.raises(AuthorizationError):
            service.invite_borrower(
                caller, tenant_id=uuid4(), party_id=uuid4(), email_hash="hash123"
            )


class TestPortalSafePrimitives:
    def test_activate_account_no_rbac_required(self) -> None:
        service, repo, audit = _make_service()
        account, raw_token = PortalAccount.invite(
            tenant_id=uuid4(), party_id=uuid4(), email_hash="hash123"
        )
        repo.save_account(account)

        activated = service.activate_account(account, raw_token)
        assert activated.status == "ACTIVE"
        assert audit.records[-1]["event_type"] == "PORTAL_ACCOUNT_ACTIVATED"

    def test_fulfill_item_no_rbac_required(self) -> None:
        service, repo, audit = _make_service()
        item = DocumentChecklistItem.create(
            tenant_id=uuid4(),
            application_id=uuid4(),
            label="Bank statement",
            document_type="BANK_STATEMENT",
            requested_by_user_id=uuid4(),
        )
        repo.save_item(item)

        document_id = uuid4()
        fulfilled = service.fulfill_item(item, document_id)
        assert fulfilled.status == "RECEIVED"
        assert fulfilled.fulfilled_document_id == document_id
        assert audit.records[-1]["event_type"] == "CHECKLIST_ITEM_FULFILLED"

    def test_get_items_for_application(self) -> None:
        service, repo, _audit = _make_service()
        app_id = uuid4()
        item = DocumentChecklistItem.create(
            tenant_id=uuid4(),
            application_id=app_id,
            label="Bank statement",
            document_type="BANK_STATEMENT",
            requested_by_user_id=uuid4(),
        )
        repo.save_item(item)
        assert service.get_items_for_application(app_id) == [item]
