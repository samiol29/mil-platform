"""Add finding.findings — immutable AI-generated conclusions (US2 Sprint 4).

Stores one holistic, inference-derived Finding per application per inference
model version. Rows are immutable and never updated.

Determinism (Principle XII): (application_id, model_version) is unique — the
same application evaluated under the same inference model version cannot
produce a duplicate Finding.

Note: policy_pack_id (present in the target data model at
specs/001-mil-platform-spec/data-model.md) is intentionally omitted, for the
same reason evidence.evidence_items.policy_pack_id was omitted in migration
0005 — the Policy Pack bounded context does not exist yet (a later sprint).

Does not create finding.finding_party_refs, evidence.evidence_snapshots, or
any review/policy tables — out of scope for this sprint.

Tables created:
    finding.findings — immutable AI-generated conclusion per (application, model version)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS finding")

    # ------------------------------------------------------------------
    # finding.findings
    #
    # FK dependencies:
    #   application_id   → core.applications.id              (owning application)
    #   workflow_run_id  → orchestrator.workflow_runs.id      (producing run / lineage)
    #
    # Immutable: created once by the Finding worker, never updated.
    # ------------------------------------------------------------------
    op.create_table(
        "findings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("workflow_run_id", sa.UUID(), nullable=False),
        sa.Column("finding_type", sa.String(100), nullable=False),
        sa.Column("lifecycle_state", sa.String(50), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("evidence_summary", sa.Text(), nullable=False),
        sa.Column("confidence_label", sa.String(100), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Numeric(4, 3), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(100), nullable=False),
        sa.Column("extraction_version", sa.String(100), nullable=False),
        sa.Column("evidence_item_ids", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["core.applications.id"],
            name=op.f("fk_findings_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"],
            ["orchestrator.workflow_runs.id"],
            name=op.f("fk_findings_workflow_run_id_workflow_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_findings")),
        sa.UniqueConstraint(
            "application_id",
            "model_version",
            name="uq_findings_application_model_version",
        ),
        schema="finding",
    )

    # Primary lookup paths.
    op.create_index(
        op.f("ix_finding_findings_application_id"),
        "findings",
        ["application_id"],
        unique=False,
        schema="finding",
    )
    op.create_index(
        op.f("ix_finding_findings_workflow_run_id"),
        "findings",
        ["workflow_run_id"],
        unique=False,
        schema="finding",
    )
    op.create_index(
        op.f("ix_finding_findings_tenant_id"),
        "findings",
        ["tenant_id"],
        unique=False,
        schema="finding",
    )


def downgrade() -> None:
    op.drop_table("findings", schema="finding")
    op.execute("DROP SCHEMA IF EXISTS finding")
