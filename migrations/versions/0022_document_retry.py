"""Add Document.retry_count (final product polish sprint).

Additive, nullable-safe column supporting genuine document ingestion retry:
tracks how many times a FAILED document's OCR/Extraction pipeline has been
re-triggered, surfaced in processing feedback ("Attempt 2 of 3") and used to
derive a distinguishing idempotency key per retry attempt.

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("documents", "retry_count", schema="core")
