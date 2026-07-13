"""Add identity schema — tenant_configurations, api_keys (Enterprise Administration, spec 005 Wave 1).

``core.users``/``core.roles``/``core.role_assignments`` already exist since
migration 0001 — this migration adds only the two genuinely new entities
Enterprise Administration introduces (spec §15): tenant-level configuration
and scoped/expiring API keys. Both FK to ``core.users`` (the existing table),
not a duplicate "identity.users" table — there is exactly one users table in
this platform.

``api_keys.expires_at`` is NOT NULL by design (Constitution Principle V,
least-privilege) — there is no schema-level path to create a permanent,
unexpiring key.

Tables created:
    identity.tenant_configurations — arbitrary tenant-scoped key/value config
    identity.api_keys              — scoped, expiring, revocable service credentials

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS identity")

    # ------------------------------------------------------------------
    # identity.tenant_configurations
    #
    # FK dependencies:
    #   updated_by_user_id → core.users.id
    # ------------------------------------------------------------------
    op.create_table(
        "tenant_configurations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("config_key", sa.String(255), nullable=False),
        sa.Column("config_value", sa.JSON(), nullable=False),
        sa.Column("updated_by_user_id", sa.UUID(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["core.users.id"],
            name=op.f("fk_tenant_configurations_updated_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_configurations")),
        sa.UniqueConstraint(
            "tenant_id", "config_key", name="uq_tenant_configurations_tenant_key"
        ),
        schema="identity",
    )
    op.create_index(
        op.f("ix_identity_tenant_configurations_tenant_id"),
        "tenant_configurations",
        ["tenant_id"],
        unique=False,
        schema="identity",
    )

    # ------------------------------------------------------------------
    # identity.api_keys
    #
    # FK dependencies:
    #   created_by_user_id → core.users.id
    # ------------------------------------------------------------------
    op.create_table(
        "api_keys",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hashed_key", sa.String(128), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["core.users.id"],
            name=op.f("fk_api_keys_created_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_keys")),
        sa.UniqueConstraint("hashed_key", name="uq_api_keys_hashed_key"),
        schema="identity",
    )
    op.create_index(
        op.f("ix_identity_api_keys_tenant_id"),
        "api_keys",
        ["tenant_id"],
        unique=False,
        schema="identity",
    )


def downgrade() -> None:
    # destructive-migration-approved
    op.drop_table("api_keys", schema="identity")
    op.drop_table("tenant_configurations", schema="identity")
    op.execute("DROP SCHEMA IF EXISTS identity")
