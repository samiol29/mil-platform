"""
ORM models for the Customer Portal bounded context (spec 005-enterprise-
platform §12, Wave 4).

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from mil.kernel.db import Base
from mil.kernel.errors import AuthenticationError, ConflictError, ValidationError

INVITED = "INVITED"
ACTIVE = "ACTIVE"
SUSPENDED = "SUSPENDED"

REQUESTED = "REQUESTED"
RECEIVED = "RECEIVED"
WAIVED = "WAIVED"


def hash_token(raw_token: str) -> str:
    """SHA-256 hash of a raw invitation token — only the hash is ever persisted."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class PortalAccount(Base):
    """
    A borrower's Customer Portal identity, tied to exactly one ``Party``.

    ``email_hash`` mirrors ``identity.User.email_hash``'s exact discipline
    — MIL never stores a borrower's plaintext email. The raw email is
    supplied only transiently, at invite time, by the inviting internal
    user, hashed immediately, and never persisted or logged in plaintext.

    ``invitation_token_hash`` is cleared (set to ``None``) once the account
    is activated — an already-consumed token can never be replayed.
    """

    __tablename__ = "portal_accounts"
    __table_args__ = ({"schema": "portal"},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    party_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.parties.id"), nullable=False, unique=True
    )
    email_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=INVITED)
    invitation_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @classmethod
    def invite(
        cls, *, tenant_id: UUID, party_id: UUID, email_hash: str
    ) -> tuple[PortalAccount, str]:
        """
        Create a new, ``INVITED`` portal account and a fresh raw activation
        token. Returns ``(account, raw_token)`` — the raw token is never
        persisted (only its hash is); the caller is responsible for
        delivering it to the borrower out-of-band (no email/SMS provider
        exists in this platform today — an honest, disclosed gap, not a
        fabricated delivery mechanism).
        """
        raw_token = secrets.token_urlsafe(32)
        return (
            cls(
                id=uuid4(),
                tenant_id=tenant_id,
                party_id=party_id,
                email_hash=email_hash,
                status=INVITED,
                invitation_token_hash=hash_token(raw_token),
                invited_at=datetime.now(UTC),
            ),
            raw_token,
        )

    def activate(self, raw_token: str) -> None:
        """
        Activate the account if ``raw_token`` matches the stored hash.

        Raises ``ConflictError`` if already active/suspended, or
        ``AuthenticationError`` if the token does not match — deliberately
        a generic authentication failure (never distinguishing "wrong
        token" from "already activated" to a caller who isn't already
        authenticated) except via the explicit ``ConflictError`` path for
        an account that legitimately has no more pending invitation.
        """
        if self.status != INVITED:
            raise ConflictError(f"PortalAccount {self.id} is not in INVITED status")
        if self.invitation_token_hash != hash_token(raw_token):
            raise AuthenticationError("Invalid or expired activation token")
        self.status = ACTIVE
        self.activated_at = datetime.now(UTC)
        self.invitation_token_hash = None

    def suspend(self) -> None:
        """Suspend the account, revoking further portal access. Idempotent."""
        self.status = SUSPENDED

    def __repr__(self) -> str:
        return f"<PortalAccount id={self.id} party={self.party_id} status={self.status}>"


class DocumentChecklistItem(Base):
    """
    One document request against an application, optionally scoped to a
    specific party. Created by an Underwriter/RM; fulfilled when a
    borrower uploads a matching document (through the existing, unchanged
    upload contract — no new ingestion pipeline).
    """

    __tablename__ = "document_checklist_items"
    __table_args__ = ({"schema": "portal"},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("core.applications.id"), nullable=False)
    party_id: Mapped[UUID | None] = mapped_column(ForeignKey("core.parties.id"), nullable=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=REQUESTED)
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("core.users.id"), nullable=False)
    fulfilled_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core.documents.id"), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        application_id: UUID,
        label: str,
        document_type: str,
        requested_by_user_id: UUID,
        party_id: UUID | None = None,
    ) -> DocumentChecklistItem:
        if not label or not label.strip():
            raise ValidationError("label must not be empty", field="label")
        if not document_type or not document_type.strip():
            raise ValidationError("document_type must not be empty", field="document_type")
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            application_id=application_id,
            party_id=party_id,
            label=label.strip(),
            document_type=document_type.strip(),
            status=REQUESTED,
            requested_by_user_id=requested_by_user_id,
            requested_at=datetime.now(UTC),
        )

    def fulfill(self, document_id: UUID) -> None:
        """Mark this item RECEIVED, linking the document that fulfilled it."""
        if self.status != REQUESTED:
            raise ConflictError(f"DocumentChecklistItem {self.id} is not in REQUESTED status")
        self.status = RECEIVED
        self.fulfilled_document_id = document_id

    def waive(self) -> None:
        """Mark this item WAIVED — no longer required (a human decision, Principle I)."""
        if self.status != REQUESTED:
            raise ConflictError(f"DocumentChecklistItem {self.id} is not in REQUESTED status")
        self.status = WAIVED

    def __repr__(self) -> str:
        return f"<DocumentChecklistItem id={self.id} application={self.application_id} status={self.status}>"
