"""Add portal schema (Customer Portal, spec 005-enterprise-platform §12,
Wave 4).

Tables created:
    portal.portal_accounts          — borrower portal identities
    portal.document_checklist_items — document requests against an application

A correction from the spec's original wording, which placed
``document_checklist_items`` in the ``core`` schema: this migration places
it in the new ``portal`` schema instead, matching every other Wave 2/3
module's own-schema convention (``assignment.*``, ``borrower_identity.*``,
etc.) rather than the original MVP's ``core`` schema, which is reserved for
the foundational application/party/document entities.

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS portal")

    op.create_table(
        "portal_accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("party_id", sa.UUID(), nullable=False),
        sa.Column("email_hash", sa.String(128), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'INVITED'")),
        sa.Column("invitation_token_hash", sa.String(128), nullable=True),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["party_id"], ["core.parties.id"], name=op.f("fk_portal_accounts_party_id_parties")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_portal_accounts")),
        sa.UniqueConstraint("party_id", name=op.f("uq_portal_accounts_party_id")),
        schema="portal",
    )
    op.create_index(
        op.f("ix_portal_portal_accounts_tenant_id"),
        "portal_accounts", ["tenant_id"], unique=False, schema="portal",
    )

    op.create_table(
        "document_checklist_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("party_id", sa.UUID(), nullable=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("document_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'REQUESTED'")),
        sa.Column("requested_by_user_id", sa.UUID(), nullable=False),
        sa.Column("fulfilled_document_id", sa.UUID(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"], ["core.applications.id"],
            name=op.f("fk_document_checklist_items_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["party_id"], ["core.parties.id"],
            name=op.f("fk_document_checklist_items_party_id_parties"),
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["core.users.id"],
            name=op.f("fk_document_checklist_items_requested_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["fulfilled_document_id"], ["core.documents.id"],
            name=op.f("fk_document_checklist_items_fulfilled_document_id_documents"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_checklist_items")),
        schema="portal",
    )
    op.create_index(
        op.f("ix_portal_document_checklist_items_application_id"),
        "document_checklist_items", ["application_id"], unique=False, schema="portal",
    )


def downgrade() -> None:
    # destructive-migration-approved
    op.drop_table("document_checklist_items", schema="portal")
    op.drop_table("portal_accounts", schema="portal")
    op.execute("DROP SCHEMA IF EXISTS portal")
