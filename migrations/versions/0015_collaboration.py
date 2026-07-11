"""Add mentioned_user_ids/edited_at/deleted_at to review_comments
(spec 005-enterprise-platform §9, Collaboration, Wave 1).

``review.review_comments`` already exists (migration 0008) and is scoped by
``review_session_id`` — i.e. a comment discusses one Finding's review, not
an application-wide thread (ground truth confirmed against
``src/mil/review/models.py`` before this migration was written; the
spec was corrected from an earlier application-level-thread design to match
this — see spec.md §9 and the final Wave 1 implementation report).

Additive columns only:
    mentioned_user_ids — JSON list of user ids the comment @-mentions
    edited_at           — set on edit (author-only, within a 5-minute window)
    deleted_at          — soft-delete marker (never a hard delete)

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "review_comments",
        sa.Column(
            "mentioned_user_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")
        ),
        schema="review",
    )
    op.add_column(
        "review_comments",
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        schema="review",
    )
    op.add_column(
        "review_comments",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="review",
    )


def downgrade() -> None:
    op.drop_column("review_comments", "deleted_at", schema="review")
    op.drop_column("review_comments", "edited_at", schema="review")
    op.drop_column("review_comments", "mentioned_user_ids", schema="review")
