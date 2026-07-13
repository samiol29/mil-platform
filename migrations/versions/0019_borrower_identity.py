"""Add borrower_identity schema + Party identifier columns
(spec 005-enterprise-platform §5, Wave 3 — Borrower Identity Resolution).

``core.parties`` gets two additive, nullable columns
(``external_identifier_hash``/``identifier_type``) — a SHA-256 hash of a
real external identifier the LOS supplied, never the raw value (same
discipline as ``identity.users.email_hash``). No SSN/DOB/address/phone/
email columns are added anywhere — MIL does not store that PII (Principle
V, confirmed by direct inspection before this migration was written).

Tables created:
    borrower_identity.identity_match_candidates — advisory match suggestions
    borrower_identity.borrower_identities        — confirmed resolved identities
    borrower_identity.borrower_identity_members  — party/application links

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "parties",
        sa.Column("external_identifier_hash", sa.String(128), nullable=True),
        schema="core",
    )
    op.add_column(
        "parties",
        sa.Column("identifier_type", sa.String(50), nullable=True),
        schema="core",
    )
    op.create_index(
        op.f("ix_core_parties_external_identifier_hash"),
        "parties",
        ["external_identifier_hash"],
        unique=False,
        schema="core",
    )

    op.execute("CREATE SCHEMA IF NOT EXISTS borrower_identity")

    op.create_table(
        "identity_match_candidates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("party_id", sa.UUID(), nullable=False),
        sa.Column("candidate_party_id", sa.UUID(), nullable=False),
        sa.Column("match_score", sa.Numeric(4, 3), nullable=False),
        sa.Column("match_basis", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("reviewed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["party_id"], ["core.parties.id"],
            name=op.f("fk_identity_match_candidates_party_id_parties"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_party_id"], ["core.parties.id"],
            name=op.f("fk_identity_match_candidates_candidate_party_id_parties"),
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"], ["core.users.id"],
            name=op.f("fk_identity_match_candidates_reviewed_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_identity_match_candidates")),
        schema="borrower_identity",
    )
    op.create_index(
        op.f("ix_borrower_identity_identity_match_candidates_party_id"),
        "identity_match_candidates", ["party_id"], unique=False, schema="borrower_identity",
    )
    op.create_index(
        op.f("ix_borrower_identity_identity_match_candidates_status"),
        "identity_match_candidates", ["status"], unique=False, schema="borrower_identity",
    )

    op.create_table(
        "borrower_identities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("primary_display_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_borrower_identities")),
        schema="borrower_identity",
    )
    op.create_index(
        op.f("ix_borrower_identity_borrower_identities_tenant_id"),
        "borrower_identities", ["tenant_id"], unique=False, schema="borrower_identity",
    )

    op.create_table(
        "borrower_identity_members",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("borrower_identity_id", sa.UUID(), nullable=False),
        sa.Column("party_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("linked_by_user_id", sa.UUID(), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unlinked_by_user_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["borrower_identity_id"], ["borrower_identity.borrower_identities.id"],
            name=op.f("fk_borrower_identity_members_borrower_identity_id_borrower_identities"),
        ),
        sa.ForeignKeyConstraint(
            ["party_id"], ["core.parties.id"],
            name=op.f("fk_borrower_identity_members_party_id_parties"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["core.applications.id"],
            name=op.f("fk_borrower_identity_members_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["linked_by_user_id"], ["core.users.id"],
            name=op.f("fk_borrower_identity_members_linked_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["unlinked_by_user_id"], ["core.users.id"],
            name=op.f("fk_borrower_identity_members_unlinked_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_borrower_identity_members")),
        schema="borrower_identity",
    )
    op.create_index(
        op.f("ix_borrower_identity_borrower_identity_members_borrower_identity_id"),
        "borrower_identity_members", ["borrower_identity_id"], unique=False,
        schema="borrower_identity",
    )
    op.create_index(
        op.f("ix_borrower_identity_borrower_identity_members_party_id"),
        "borrower_identity_members", ["party_id"], unique=False, schema="borrower_identity",
    )


def downgrade() -> None:
    # destructive-migration-approved
    op.drop_table("borrower_identity_members", schema="borrower_identity")
    op.drop_table("borrower_identities", schema="borrower_identity")
    op.drop_table("identity_match_candidates", schema="borrower_identity")
    op.execute("DROP SCHEMA IF EXISTS borrower_identity")
    op.drop_column("parties", "identifier_type", schema="core")
    op.drop_column("parties", "external_identifier_hash", schema="core")
