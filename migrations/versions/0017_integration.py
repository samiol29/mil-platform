"""Add integration schema — los_connections, los_sync_events
(spec 005-enterprise-platform §2, Wave 2 — LOS Integration Layer).

The ``LOSAdapter`` interface itself (``mil.kernel.providers.los_adapter``)
already existed and is unchanged by this migration — this adds only the
tenant-visible configuration record and the audit-adjacent sync/push log
that lets it be used through a real HTTP surface.

Tables created:
    integration.los_connections  — registered LOS integration configuration
    integration.los_sync_events  — append-only inbound/outbound sync/push log

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS integration")

    op.create_table(
        "los_connections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("vendor_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["core.users.id"],
            name=op.f("fk_los_connections_created_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_los_connections")),
        schema="integration",
    )
    op.create_index(
        op.f("ix_integration_los_connections_tenant_id"),
        "los_connections",
        ["tenant_id"],
        unique=False,
        schema="integration",
    )

    op.create_table(
        "los_sync_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("initiated_by_user_id", sa.UUID(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["core.applications.id"],
            name=op.f("fk_los_sync_events_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["initiated_by_user_id"],
            ["core.users.id"],
            name=op.f("fk_los_sync_events_initiated_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_los_sync_events")),
        schema="integration",
    )
    op.create_index(
        op.f("ix_integration_los_sync_events_application_id"),
        "los_sync_events",
        ["application_id"],
        unique=False,
        schema="integration",
    )
    op.create_index(
        op.f("ix_integration_los_sync_events_tenant_id"),
        "los_sync_events",
        ["tenant_id"],
        unique=False,
        schema="integration",
    )
    op.create_index(
        op.f("ix_integration_los_sync_events_outcome"),
        "los_sync_events",
        ["outcome"],
        unique=False,
        schema="integration",
    )


def downgrade() -> None:
    op.drop_table("los_sync_events", schema="integration")
    op.drop_table("los_connections", schema="integration")
    op.execute("DROP SCHEMA IF EXISTS integration")
