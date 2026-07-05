"""Add copilot schema — copilot_sessions, copilot_queries, copilot_responses (US2 Sprint 7A).

Stores the Copilot bounded-context foundation: a reviewer's interaction
session with one application, the natural-language queries asked within it,
and the responses recorded against those queries (ADR-011 — Grounded AI
Copilot).

All three tables are append-only. ``copilot_sessions`` is created once per
interaction and never updated. ``copilot_queries`` and ``copilot_responses``
are immutable, append-only rows; a response is never overwritten, and
``query_id`` is unique on ``copilot_responses`` so at most one response is
ever recorded per query (regeneration is out of scope for Sprint 7A).

Determinism / attribution (Principle XII / ADR-011 §7-8): every response
records ``prompt_version`` and ``model_version`` so a future auditor can
attribute the exact configuration that produced it, even though Copilot
responses are explicitly exempt from Finding-level bit-reproducibility
(ADR-011 §8).

Tables created:
    copilot.copilot_sessions  — one row per reviewer interaction with an application
    copilot.copilot_queries   — immutable, append-only natural-language questions
    copilot.copilot_responses — immutable, append-only answers with attribution + citations

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS copilot")

    # ------------------------------------------------------------------
    # copilot.copilot_sessions
    #
    # FK dependencies:
    #   application_id     → core.applications.id
    #   created_by_user_id → core.users.id
    #
    # Created once per interaction; no update method exists in the
    # repository or service (Sprint 7A defines no session lifecycle).
    # ------------------------------------------------------------------
    op.create_table(
        "copilot_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("correlation_id", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["core.applications.id"],
            name=op.f("fk_copilot_sessions_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["core.users.id"],
            name=op.f("fk_copilot_sessions_created_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_copilot_sessions")),
        schema="copilot",
    )
    op.create_index(
        op.f("ix_copilot_copilot_sessions_application_id"),
        "copilot_sessions",
        ["application_id"],
        unique=False,
        schema="copilot",
    )
    op.create_index(
        op.f("ix_copilot_copilot_sessions_tenant_id"),
        "copilot_sessions",
        ["tenant_id"],
        unique=False,
        schema="copilot",
    )

    # ------------------------------------------------------------------
    # copilot.copilot_queries
    #
    # FK dependencies:
    #   session_id        → copilot.copilot_sessions.id
    #   asked_by_user_id  → core.users.id
    #
    # Immutable: created once per query, never updated.
    # ------------------------------------------------------------------
    op.create_table(
        "copilot_queries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("asked_by_user_id", sa.UUID(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["copilot.copilot_sessions.id"],
            name=op.f("fk_copilot_queries_session_id_copilot_sessions"),
        ),
        sa.ForeignKeyConstraint(
            ["asked_by_user_id"],
            ["core.users.id"],
            name=op.f("fk_copilot_queries_asked_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_copilot_queries")),
        schema="copilot",
    )
    op.create_index(
        op.f("ix_copilot_copilot_queries_session_id"),
        "copilot_queries",
        ["session_id"],
        unique=False,
        schema="copilot",
    )

    # ------------------------------------------------------------------
    # copilot.copilot_responses
    #
    # FK dependencies:
    #   query_id → copilot.copilot_queries.id (UNIQUE — at most one response per query)
    #
    # Immutable: created once per response, never updated or deleted.
    # ------------------------------------------------------------------
    op.create_table(
        "copilot_responses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("query_id", sa.UUID(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["query_id"],
            ["copilot.copilot_queries.id"],
            name=op.f("fk_copilot_responses_query_id_copilot_queries"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_copilot_responses")),
        sa.UniqueConstraint("query_id", name="uq_copilot_responses_query_id"),
        schema="copilot",
    )


def downgrade() -> None:
    op.drop_table("copilot_responses", schema="copilot")
    op.drop_table("copilot_queries", schema="copilot")
    op.drop_table("copilot_sessions", schema="copilot")
    op.execute("DROP SCHEMA IF EXISTS copilot")
