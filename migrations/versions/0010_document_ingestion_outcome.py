"""Add pipeline outcome columns to core.documents.

Adds the columns the API has always declared on ``DocumentResponse`` but that
were never backed by real data: ``page_count``, ``evidence_item_count``,
``ingestion_completed_at``, ``ingestion_error``. Populated by
``Document.mark_completed()`` / ``mark_failed()`` when the DOCUMENT_INGESTION
workflow (OCR -> Extraction) reaches a terminal state.

Tables altered:
    core.documents

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("page_count", sa.Integer(), nullable=True),
        schema="core",
    )
    op.add_column(
        "documents",
        sa.Column(
            "evidence_item_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        schema="core",
    )
    op.add_column(
        "documents",
        sa.Column("ingestion_completed_at", sa.DateTime(timezone=True), nullable=True),
        schema="core",
    )
    op.add_column(
        "documents",
        sa.Column("ingestion_error", sa.Text(), nullable=True),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("documents", "ingestion_error", schema="core")
    op.drop_column("documents", "ingestion_completed_at", schema="core")
    op.drop_column("documents", "evidence_item_count", schema="core")
    op.drop_column("documents", "page_count", schema="core")
