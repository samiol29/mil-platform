"""Add review schema — review_sessions, review_actions, review_comments (US2 Sprint 6).

Stores the human review of AI-generated, policy-evaluated Findings
(Engineering Constitution Principle I — Human Decision Authority).

Normalized-schema justification: an override record is not given its own
table. Every ``review_actions`` row already carries full attribution (actor,
timestamp, reason, previous/new status, previous/new value) regardless of
``action_type`` — a dedicated override table would duplicate every one of
these columns for no additional information. An override is simply a
``review_actions`` row with ``action_type = 'OVERRIDDEN'``. See
``src/mil/review/models.py`` module docstring.

Determinism / idempotency (Principle XII / ADR-008): a Review Session is
identified by the Finding it reviews — `finding_id` is unique on
`review_sessions`. A Finding is produced once (US2 Sprint 4) and never
re-evaluated, so it is reviewed at most once; re-delivery of the job that
creates a session for the same Finding cannot produce a duplicate.

Tables created:
    review.review_sessions — mutable current-state row per Finding under review
    review.review_actions  — immutable, append-only action/override history
    review.review_comments — immutable, append-only free-text discussion

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS review")

    # ------------------------------------------------------------------
    # review.review_sessions
    #
    # FK dependencies:
    #   finding_id           → finding.findings.id           (UNIQUE — one session per Finding)
    #   application_id       → core.applications.id
    #   workflow_run_id      → orchestrator.workflow_runs.id  (lineage)
    #   policy_result_id     → policy.policy_results.id       (the evaluation that triggered review)
    #   assigned_reviewer_id → core.users.id (nullable)
    # ------------------------------------------------------------------
    op.create_table(
        "review_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("finding_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("workflow_run_id", sa.UUID(), nullable=False),
        sa.Column("policy_result_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("assigned_reviewer_id", sa.UUID(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["finding.findings.id"],
            name=op.f("fk_review_sessions_finding_id_findings"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["core.applications.id"],
            name=op.f("fk_review_sessions_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"],
            ["orchestrator.workflow_runs.id"],
            name=op.f("fk_review_sessions_workflow_run_id_workflow_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["policy_result_id"],
            ["policy.policy_results.id"],
            name=op.f("fk_review_sessions_policy_result_id_policy_results"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_reviewer_id"],
            ["core.users.id"],
            name=op.f("fk_review_sessions_assigned_reviewer_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_sessions")),
        sa.UniqueConstraint("finding_id", name="uq_review_sessions_finding_id"),
        schema="review",
    )
    op.create_index(
        op.f("ix_review_review_sessions_application_id"),
        "review_sessions",
        ["application_id"],
        unique=False,
        schema="review",
    )
    op.create_index(
        op.f("ix_review_review_sessions_tenant_id"),
        "review_sessions",
        ["tenant_id"],
        unique=False,
        schema="review",
    )
    op.create_index(
        op.f("ix_review_review_sessions_workflow_run_id"),
        "review_sessions",
        ["workflow_run_id"],
        unique=False,
        schema="review",
    )
    op.create_index(
        op.f("ix_review_review_sessions_status"),
        "review_sessions",
        ["status"],
        unique=False,
        schema="review",
    )

    # ------------------------------------------------------------------
    # review.review_actions
    #
    # FK dependencies:
    #   review_session_id → review.review_sessions.id
    #   actor_user_id      → core.users.id (nullable — SESSION_STARTED is system-driven)
    #
    # Immutable: created once per action, never updated.
    # ------------------------------------------------------------------
    op.create_table(
        "review_actions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("review_session_id", sa.UUID(), nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("previous_status", sa.String(50), nullable=False),
        sa.Column("new_status", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("previous_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_session_id"],
            ["review.review_sessions.id"],
            name=op.f("fk_review_actions_review_session_id_review_sessions"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["core.users.id"],
            name=op.f("fk_review_actions_actor_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_actions")),
        schema="review",
    )
    op.create_index(
        op.f("ix_review_review_actions_review_session_id"),
        "review_actions",
        ["review_session_id"],
        unique=False,
        schema="review",
    )

    # ------------------------------------------------------------------
    # review.review_comments
    #
    # FK dependencies:
    #   review_session_id → review.review_sessions.id
    #   author_user_id     → core.users.id
    #
    # Immutable: created once per comment, never updated.
    # ------------------------------------------------------------------
    op.create_table(
        "review_comments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("review_session_id", sa.UUID(), nullable=False),
        sa.Column("author_user_id", sa.UUID(), nullable=False),
        sa.Column("comment_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_session_id"],
            ["review.review_sessions.id"],
            name=op.f("fk_review_comments_review_session_id_review_sessions"),
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"],
            ["core.users.id"],
            name=op.f("fk_review_comments_author_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_comments")),
        schema="review",
    )
    op.create_index(
        op.f("ix_review_review_comments_review_session_id"),
        "review_comments",
        ["review_session_id"],
        unique=False,
        schema="review",
    )


def downgrade() -> None:
    op.drop_table("review_comments", schema="review")
    op.drop_table("review_actions", schema="review")
    op.drop_table("review_sessions", schema="review")
    op.execute("DROP SCHEMA IF EXISTS review")
