"""Add assignment schema — assignments, assignment_history
(spec 005-enterprise-platform §1, Wave 2 — RM/Banker Workspace).

``assignments`` is the current "who owns/reviews this application" record,
one row per application (``UNIQUE(application_id)``). ``assignment_history``
is the append-only log of every prior state, snapshotted before each
reassignment — mirrors the immutability discipline already applied to
``core.role_assignments`` (soft-revocation) and ``review.review_actions``.

Tables created:
    assignment.assignments         — current ownership/review assignment
    assignment.assignment_history  — append-only history of prior assignments

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS assignment")

    op.create_table(
        "assignments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("reviewer_user_id", sa.UUID(), nullable=True),
        sa.Column("assigned_by_user_id", sa.UUID(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["core.applications.id"],
            name=op.f("fk_assignments_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["core.users.id"], name=op.f("fk_assignments_owner_user_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_user_id"],
            ["core.users.id"],
            name=op.f("fk_assignments_reviewer_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_user_id"],
            ["core.users.id"],
            name=op.f("fk_assignments_assigned_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assignments")),
        sa.UniqueConstraint("application_id", name="uq_assignments_application_id"),
        schema="assignment",
    )
    op.create_index(
        op.f("ix_assignment_assignments_owner_user_id"),
        "assignments",
        ["owner_user_id"],
        unique=False,
        schema="assignment",
    )
    op.create_index(
        op.f("ix_assignment_assignments_reviewer_user_id"),
        "assignments",
        ["reviewer_user_id"],
        unique=False,
        schema="assignment",
    )

    op.create_table(
        "assignment_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("reviewer_user_id", sa.UUID(), nullable=True),
        sa.Column("assigned_by_user_id", sa.UUID(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["core.applications.id"],
            name=op.f("fk_assignment_history_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["core.users.id"],
            name=op.f("fk_assignment_history_owner_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_user_id"],
            ["core.users.id"],
            name=op.f("fk_assignment_history_reviewer_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_user_id"],
            ["core.users.id"],
            name=op.f("fk_assignment_history_assigned_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assignment_history")),
        schema="assignment",
    )
    op.create_index(
        op.f("ix_assignment_assignment_history_application_id"),
        "assignment_history",
        ["application_id"],
        unique=False,
        schema="assignment",
    )


def downgrade() -> None:
    # destructive-migration-approved
    op.drop_table("assignment_history", schema="assignment")
    op.drop_table("assignments", schema="assignment")
    op.execute("DROP SCHEMA IF EXISTS assignment")
