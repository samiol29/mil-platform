"""Add evidence.evidence_items — immutable extracted facts (US2 Sprint 3).

Stores a single fact extracted from a document, separately from the source
OCR output (core.document_ocr_results). Rows are immutable and never updated.

Determinism (Principle XII): (document_id, extraction_model_version,
evidence_type) is unique — the same document under the same extraction engine
version cannot produce a duplicate row for the same fact.

Note: policy_pack_id (present in the target data model at
specs/001-mil-platform-spec/data-model.md) is intentionally omitted. The
Policy Pack bounded context does not exist yet (US2 Sprint 5+); a later
migration adds that column once core.policy_packs exists.

Tables created:
    evidence.evidence_items — immutable extracted fact per (document, extraction version, field)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS evidence")

    # ------------------------------------------------------------------
    # evidence.evidence_items
    #
    # FK dependencies:
    #   application_id   → core.applications.id              (owning application)
    #   party_id         → core.parties.id                    (nullable — subject party)
    #   document_id      → core.documents.id                  (source document)
    #   workflow_run_id  → orchestrator.workflow_runs.id       (producing run / lineage)
    #   supersedes_id    → evidence.evidence_items.id          (nullable, self-referential)
    #
    # Immutable: created once by the Extraction worker, never updated.
    # ------------------------------------------------------------------
    op.create_table(
        "evidence_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("party_id", sa.UUID(), nullable=True),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("workflow_run_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("evidence_type", sa.String(100), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_numeric", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("field_location", sa.JSON(), nullable=True),
        sa.Column("extraction_confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("extraction_method", sa.String(100), nullable=False),
        sa.Column("extraction_model_version", sa.String(100), nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("supersedes_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["core.applications.id"],
            name=op.f("fk_evidence_items_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["party_id"],
            ["core.parties.id"],
            name=op.f("fk_evidence_items_party_id_parties"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["core.documents.id"],
            name=op.f("fk_evidence_items_document_id_documents"),
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"],
            ["orchestrator.workflow_runs.id"],
            name=op.f("fk_evidence_items_workflow_run_id_workflow_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["evidence.evidence_items.id"],
            name=op.f("fk_evidence_items_supersedes_id_evidence_items"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence_items")),
        sa.UniqueConstraint(
            "document_id",
            "extraction_model_version",
            "evidence_type",
            name="uq_evidence_items_document_version_type",
        ),
        schema="evidence",
    )

    # Primary lookup paths.
    op.create_index(
        op.f("ix_evidence_evidence_items_document_id"),
        "evidence_items",
        ["document_id"],
        unique=False,
        schema="evidence",
    )
    op.create_index(
        op.f("ix_evidence_evidence_items_application_id"),
        "evidence_items",
        ["application_id"],
        unique=False,
        schema="evidence",
    )
    op.create_index(
        op.f("ix_evidence_evidence_items_workflow_run_id"),
        "evidence_items",
        ["workflow_run_id"],
        unique=False,
        schema="evidence",
    )
    op.create_index(
        op.f("ix_evidence_evidence_items_tenant_id"),
        "evidence_items",
        ["tenant_id"],
        unique=False,
        schema="evidence",
    )


def downgrade() -> None:
    op.drop_table("evidence_items", schema="evidence")
    op.execute("DROP SCHEMA IF EXISTS evidence")
