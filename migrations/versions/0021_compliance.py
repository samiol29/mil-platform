"""Add compliance schema (Security & Compliance, spec 005-enterprise-
platform §16, Wave 4).

Tables created:
    compliance.data_retention_policies — per-tenant, per-category retention config
    compliance.consent_records         — explicit, timestamped, versioned consent

Both tables carry the DB-level CHECK constraints the spec calls for:
DELETE is structurally disallowed for AUDIT_EVENT/EVIDENCE retention
policies (Principle VIII), and a consent record must reference exactly one
of party_id/portal_account_id.

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS compliance")

    op.create_table(
        "data_retention_policies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("data_category", sa.String(50), nullable=False),
        sa.Column("retention_period_days", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.CheckConstraint(
            "NOT (data_category IN ('AUDIT_EVENT', 'EVIDENCE') AND action = 'DELETE')",
            name=op.f("ck_data_retention_policies_no_delete_audit_evidence"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_retention_policies")),
        schema="compliance",
    )
    op.create_index(
        op.f("ix_compliance_data_retention_policies_tenant_id"),
        "data_retention_policies", ["tenant_id"], unique=False, schema="compliance",
    )

    op.create_table(
        "consent_records",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("party_id", sa.UUID(), nullable=True),
        sa.Column("portal_account_id", sa.UUID(), nullable=True),
        sa.Column("consent_type", sa.String(100), nullable=False),
        sa.Column("consent_text_version", sa.String(50), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(party_id IS NOT NULL AND portal_account_id IS NULL) OR "
            "(party_id IS NULL AND portal_account_id IS NOT NULL)",
            name=op.f("ck_consent_records_exactly_one_subject"),
        ),
        sa.ForeignKeyConstraint(
            ["party_id"], ["core.parties.id"], name=op.f("fk_consent_records_party_id_parties")
        ),
        sa.ForeignKeyConstraint(
            ["portal_account_id"], ["portal.portal_accounts.id"],
            name=op.f("fk_consent_records_portal_account_id_portal_accounts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consent_records")),
        schema="compliance",
    )


def downgrade() -> None:
    op.drop_table("consent_records", schema="compliance")
    op.drop_table("data_retention_policies", schema="compliance")
    op.execute("DROP SCHEMA IF EXISTS compliance")
