"""Persistence gateway for the Customer Portal bounded context."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from mil.portal.models import DocumentChecklistItem, PortalAccount

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session


class PortalRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # PortalAccount
    # ------------------------------------------------------------------

    def save_account(self, account: PortalAccount) -> None:
        self._session.add(account)
        self._session.flush()

    def get_account_by_id(self, account_id: UUID) -> PortalAccount | None:
        return self._session.get(PortalAccount, account_id)

    def get_account_for_party(self, party_id: UUID) -> PortalAccount | None:
        stmt = select(PortalAccount).where(PortalAccount.party_id == party_id)
        return self._session.scalars(stmt).one_or_none()

    # ------------------------------------------------------------------
    # DocumentChecklistItem
    # ------------------------------------------------------------------

    def save_item(self, item: DocumentChecklistItem) -> None:
        self._session.add(item)
        self._session.flush()

    def get_item_by_id(self, item_id: UUID) -> DocumentChecklistItem | None:
        return self._session.get(DocumentChecklistItem, item_id)

    def get_items_for_application(self, application_id: UUID) -> list[DocumentChecklistItem]:
        stmt = (
            select(DocumentChecklistItem)
            .where(DocumentChecklistItem.application_id == application_id)
            .order_by(DocumentChecklistItem.requested_at.asc())
        )
        return list(self._session.scalars(stmt))
