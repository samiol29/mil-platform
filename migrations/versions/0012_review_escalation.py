"""Add escalation columns to review.review_sessions and review.review_actions.

Design (approved after a focused domain-design review — see docs/archive/HANDOFF.md):
escalation is a non-terminal `ReviewSession` status, resolved by the same
existing verify/override/reject actions rather than a separate resolution
action or a separate bounded context — the same normalized-schema
justification `0008_review_schema.py` already applied to overrides
("a dedicated table would duplicate columns for no additional information")
applies here too.

Columns added:
    review.review_sessions.escalated_to_role     — mutable, current-state:
        which role's queue this session is now in (NULL when not escalated).
    review.review_sessions.escalated_to_user_id  — mutable, current-state:
        nullable direct-assignment slot for a future "escalate to a specific
        person" refinement; NULL means "any holder of the target role."
    review.review_actions.target_role            — immutable snapshot of the
        role an ESCALATED action targeted, at the moment it was recorded.
    review.review_actions.target_user_id         — immutable snapshot of the
        specific user (if any) that action targeted.

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "review_sessions",
        sa.Column("escalated_to_role", sa.String(50), nullable=True),
        schema="review",
    )
    op.add_column(
        "review_sessions",
        sa.Column("escalated_to_user_id", sa.UUID(), nullable=True),
        schema="review",
    )
    op.create_foreign_key(
        op.f("fk_review_sessions_escalated_to_user_id_users"),
        "review_sessions",
        "users",
        ["escalated_to_user_id"],
        ["id"],
        source_schema="review",
        referent_schema="core",
    )

    op.add_column(
        "review_actions",
        sa.Column("target_role", sa.String(50), nullable=True),
        schema="review",
    )
    op.add_column(
        "review_actions",
        sa.Column("target_user_id", sa.UUID(), nullable=True),
        schema="review",
    )
    op.create_foreign_key(
        op.f("fk_review_actions_target_user_id_users"),
        "review_actions",
        "users",
        ["target_user_id"],
        ["id"],
        source_schema="review",
        referent_schema="core",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_review_actions_target_user_id_users"), "review_actions", schema="review"
    )
    op.drop_column("review_actions", "target_user_id", schema="review")
    op.drop_column("review_actions", "target_role", schema="review")

    op.drop_constraint(
        op.f("fk_review_sessions_escalated_to_user_id_users"), "review_sessions", schema="review"
    )
    op.drop_column("review_sessions", "escalated_to_user_id", schema="review")
    op.drop_column("review_sessions", "escalated_to_role", schema="review")
