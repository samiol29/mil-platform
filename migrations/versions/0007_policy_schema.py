"""Add policy schema — policy_packs, policy_rules, policy_results (US2 Sprint 5).

Stores Policy Pack lifecycle metadata, their rule catalogues, and the
immutable outcome of evaluating a Finding against a Policy Pack.

Schema placement note: the target data model
(specs/001-mil-platform-spec/data-model.md) places `policy_packs` under the
`core` schema. This migration instead gives Policy its own dedicated schema,
mirroring the pattern already established for `evidence` (migration 0005) and
`finding` (migration 0006) — every intelligence-pipeline bounded context owns
its schema rather than sharing `core`. This is an explicit, requested
deviation for this sprint, not an architectural contradiction.

Determinism (Principle XII): (finding_id, policy_version) is unique on
policy_results — the same Finding evaluated under the same Policy provider
version cannot produce a duplicate result.

Only one Policy Pack per tenant may be active at a time (data-model.md
invariant) — enforced by a partial unique index on policy_packs(tenant_id)
where the pack is active (activated_at IS NOT NULL AND deactivated_at IS NULL).

Tables created:
    policy.policy_packs   — Policy Pack lifecycle metadata
    policy.policy_rules   — rule catalogue belonging to a pack
    policy.policy_results — immutable Policy evaluation outcome per (finding, policy version)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS policy")

    # ------------------------------------------------------------------
    # policy.policy_packs
    #
    # FK dependencies:
    #   created_by → core.users.id (nullable — system-created packs have none)
    # ------------------------------------------------------------------
    op.create_table(
        "policy_packs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("jurisdiction", sa.String(100), nullable=True),
        sa.Column("content_hash", sa.String(128), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["core.users.id"],
            name=op.f("fk_policy_packs_created_by_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_packs")),
        schema="policy",
    )
    op.create_index(
        op.f("ix_policy_policy_packs_tenant_id"),
        "policy_packs",
        ["tenant_id"],
        unique=False,
        schema="policy",
    )
    # At most one active Policy Pack per tenant (data-model.md invariant).
    op.create_index(
        "uq_policy_packs_one_active_per_tenant",
        "policy_packs",
        ["tenant_id"],
        unique=True,
        schema="policy",
        postgresql_where=sa.text("activated_at IS NOT NULL AND deactivated_at IS NULL"),
    )

    # ------------------------------------------------------------------
    # policy.policy_rules
    #
    # FK dependencies:
    #   policy_pack_id → policy.policy_packs.id
    # ------------------------------------------------------------------
    op.create_table(
        "policy_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("policy_pack_id", sa.UUID(), nullable=False),
        sa.Column("rule_key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["policy_pack_id"],
            ["policy.policy_packs.id"],
            name=op.f("fk_policy_rules_policy_pack_id_policy_packs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_rules")),
        sa.UniqueConstraint(
            "policy_pack_id", "rule_key", name="uq_policy_rules_pack_rule_key"
        ),
        schema="policy",
    )
    op.create_index(
        op.f("ix_policy_policy_rules_policy_pack_id"),
        "policy_rules",
        ["policy_pack_id"],
        unique=False,
        schema="policy",
    )

    # ------------------------------------------------------------------
    # policy.policy_results
    #
    # FK dependencies:
    #   finding_id       → finding.findings.id
    #   application_id   → core.applications.id
    #   workflow_run_id  → orchestrator.workflow_runs.id
    #   policy_pack_id   → policy.policy_packs.id
    #
    # Immutable: created once by the Policy worker, never updated.
    # ------------------------------------------------------------------
    op.create_table(
        "policy_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("finding_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("workflow_run_id", sa.UUID(), nullable=False),
        sa.Column("policy_pack_id", sa.UUID(), nullable=False),
        sa.Column("policy_version", sa.String(100), nullable=False),
        sa.Column("outcome", sa.String(50), nullable=False),
        sa.Column("triggered_rule_keys", sa.JSON(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["finding.findings.id"],
            name=op.f("fk_policy_results_finding_id_findings"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["core.applications.id"],
            name=op.f("fk_policy_results_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"],
            ["orchestrator.workflow_runs.id"],
            name=op.f("fk_policy_results_workflow_run_id_workflow_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["policy_pack_id"],
            ["policy.policy_packs.id"],
            name=op.f("fk_policy_results_policy_pack_id_policy_packs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_results")),
        sa.UniqueConstraint(
            "finding_id", "policy_version", name="uq_policy_results_finding_version"
        ),
        schema="policy",
    )
    op.create_index(
        op.f("ix_policy_policy_results_finding_id"),
        "policy_results",
        ["finding_id"],
        unique=False,
        schema="policy",
    )
    op.create_index(
        op.f("ix_policy_policy_results_application_id"),
        "policy_results",
        ["application_id"],
        unique=False,
        schema="policy",
    )
    op.create_index(
        op.f("ix_policy_policy_results_workflow_run_id"),
        "policy_results",
        ["workflow_run_id"],
        unique=False,
        schema="policy",
    )
    op.create_index(
        op.f("ix_policy_policy_results_tenant_id"),
        "policy_results",
        ["tenant_id"],
        unique=False,
        schema="policy",
    )


def downgrade() -> None:
    op.drop_table("policy_results", schema="policy")
    op.drop_table("policy_rules", schema="policy")
    op.drop_table("policy_packs", schema="policy")
    op.execute("DROP SCHEMA IF EXISTS policy")
