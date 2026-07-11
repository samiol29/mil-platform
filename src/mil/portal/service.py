"""
PortalService — use-case orchestrator for the Customer Portal bounded
context (spec 005-enterprise-platform §12, Wave 4).

Two distinct groups of methods, matching the spec's own explicit boundary:

- **Internal-staff methods** (`create_checklist_item`, `get_checklist_for_
  application`, `waive_item`, `invite_borrower`) take an
  ``AuthenticatedUser`` and self-check ``Permission.MANAGE_CHECKLIST`` (or
  ``Permission.READ_APPLICATION`` for reads) — the existing internal RBAC
  system, exactly like every other Wave 2/3 service.
- **Portal-safe primitives** (`get_items_for_application`, `fulfill_item`,
  `get_account_for_party`, `activate_account`, `issue_session`) take **no**
  ``AuthenticatedUser`` and perform **no** internal-RBAC check — portal
  accounts are never evaluated through ``mil.kernel.security``. Scope
  enforcement for these happens entirely in the composition layer
  (``mil.api.deps``'s ``PortalWorkspace``), which resolves the caller's
  ``applicationId`` strictly from the *verified* portal session token's
  ``party_id`` — never from a client-supplied value — so a portal caller
  can only ever reach their own application's checklist.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mil.kernel.security import Permission, require_permission
from mil.portal.models import DocumentChecklistItem, PortalAccount

if TYPE_CHECKING:
    from uuid import UUID

    from mil.audit.writer import AuditWriter
    from mil.kernel.security import AuthenticatedUser
    from mil.portal.repository import PortalRepository


class PortalService:
    def __init__(self, repository: PortalRepository, audit: AuditWriter) -> None:
        self._repo = repository
        self._audit = audit

    # ------------------------------------------------------------------
    # Internal-staff methods (self-checking internal RBAC)
    # ------------------------------------------------------------------

    def create_checklist_item(
        self,
        caller: AuthenticatedUser,
        *,
        tenant_id: UUID,
        application_id: UUID,
        label: str,
        document_type: str,
        party_id: UUID | None = None,
    ) -> DocumentChecklistItem:
        require_permission(caller, Permission.MANAGE_CHECKLIST)
        item = DocumentChecklistItem.create(
            tenant_id=tenant_id,
            application_id=application_id,
            label=label,
            document_type=document_type,
            requested_by_user_id=caller.user_id,
            party_id=party_id,
        )
        self._repo.save_item(item)
        self._audit.record(
            event_type="CHECKLIST_ITEM_REQUESTED",
            entity_type="DOCUMENT_CHECKLIST_ITEM",
            entity_id=item.id,
            tenant_id=tenant_id,
            application_id=application_id,
            actor_id=caller.user_id,
            event_data={"label": item.label, "document_type": item.document_type},
        )
        return item

    def get_checklist_for_application(
        self, caller: AuthenticatedUser, application_id: UUID
    ) -> list[DocumentChecklistItem]:
        require_permission(caller, Permission.READ_APPLICATION)
        return self._repo.get_items_for_application(application_id)

    def waive_item(
        self, caller: AuthenticatedUser, item: DocumentChecklistItem
    ) -> DocumentChecklistItem:
        require_permission(caller, Permission.MANAGE_CHECKLIST)
        item.waive()
        self._repo.save_item(item)
        self._audit.record(
            event_type="CHECKLIST_ITEM_WAIVED",
            entity_type="DOCUMENT_CHECKLIST_ITEM",
            entity_id=item.id,
            tenant_id=item.tenant_id,
            application_id=item.application_id,
            actor_id=caller.user_id,
            event_data={},
        )
        return item

    def invite_borrower(
        self,
        caller: AuthenticatedUser,
        *,
        tenant_id: UUID,
        party_id: UUID,
        email_hash: str,
    ) -> tuple[PortalAccount, str]:
        """
        Create (or, if already invited/active, return the existing) portal
        account for a party, plus a fresh raw activation token. Returns
        the raw token directly to the caller — no email/SMS provider
        exists in this platform (an honest, disclosed gap); the inviting
        internal user is responsible for relaying it to the borrower
        out-of-band.
        """
        require_permission(caller, Permission.MANAGE_CHECKLIST)
        existing = self._repo.get_account_for_party(party_id)
        if existing is not None:
            return existing, ""
        account, raw_token = PortalAccount.invite(
            tenant_id=tenant_id, party_id=party_id, email_hash=email_hash
        )
        self._repo.save_account(account)
        self._audit.record(
            event_type="PORTAL_ACCOUNT_INVITED",
            entity_type="PORTAL_ACCOUNT",
            entity_id=account.id,
            tenant_id=tenant_id,
            actor_id=caller.user_id,
            event_data={"party_id": str(party_id)},
        )
        return account, raw_token

    # ------------------------------------------------------------------
    # Portal-safe primitives (no internal RBAC — see module docstring)
    # ------------------------------------------------------------------

    def get_account_for_party(self, party_id: UUID) -> PortalAccount | None:
        return self._repo.get_account_for_party(party_id)

    def activate_account(self, account: PortalAccount, raw_token: str) -> PortalAccount:
        account.activate(raw_token)
        self._repo.save_account(account)
        self._audit.record(
            event_type="PORTAL_ACCOUNT_ACTIVATED",
            entity_type="PORTAL_ACCOUNT",
            entity_id=account.id,
            tenant_id=account.tenant_id,
            event_data={"initiated_by": "portal_account"},
        )
        return account

    def get_items_for_application(self, application_id: UUID) -> list[DocumentChecklistItem]:
        return self._repo.get_items_for_application(application_id)

    def fulfill_item(self, item: DocumentChecklistItem, document_id: UUID) -> DocumentChecklistItem:
        item.fulfill(document_id)
        self._repo.save_item(item)
        self._audit.record(
            event_type="CHECKLIST_ITEM_FULFILLED",
            entity_type="DOCUMENT_CHECKLIST_ITEM",
            entity_id=item.id,
            tenant_id=item.tenant_id,
            application_id=item.application_id,
            event_data={"initiated_by": "portal_account", "document_id": str(document_id)},
        )
        return item
