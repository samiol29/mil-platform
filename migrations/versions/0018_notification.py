"""Add notification schema — notifications (spec 005-enterprise-platform §13,
Wave 2).

``notifications`` is a per-recipient pointer to an existing
``audit.audit_events`` row (FK), plus read state — deliberately no
``notification_type``/``title``/``body`` columns, per the spec's own
instruction to integrate with existing audit events rather than duplicate
them.

Tables created:
    notification.notifications — per-recipient pointer + read state

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS notification")

    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("recipient_user_id", sa.UUID(), nullable=False),
        sa.Column("audit_event_id", sa.UUID(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"],
            ["core.users.id"],
            name=op.f("fk_notifications_recipient_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["audit_event_id"],
            ["audit.audit_events.id"],
            name=op.f("fk_notifications_audit_event_id_audit_events"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        schema="notification",
    )
    op.create_index(
        op.f("ix_notification_notifications_recipient_user_id"),
        "notifications",
        ["recipient_user_id"],
        unique=False,
        schema="notification",
    )
    op.create_index(
        op.f("ix_notification_notifications_read_at"),
        "notifications",
        ["read_at"],
        unique=False,
        schema="notification",
    )


def downgrade() -> None:
    op.drop_table("notifications", schema="notification")
    op.execute("DROP SCHEMA IF EXISTS notification")
