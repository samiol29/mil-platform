"""Add policy_pack_approvals table + PolicyResult.evaluated_rule_keys column
(spec 005-enterprise-platform §3/§4, Wave 1).

``policy.policy_packs`` has no ``status`` column (lifecycle is the existing
``activated_at``/``deactivated_at`` pair, migration 0007) — this migration
does not add one. ``policy_pack_approvals`` is a pure additive gate in front
of the existing activation lifecycle: a pack can only be activated once an
``APPROVED`` row exists for it (enforced in ``PolicyService
.activate_pack_if_approved``, not at the DB layer, mirroring how
``PolicyPackApproval.approve``'s self-escalation check is a service/model
invariant rather than a DB constraint — the requester/decider are both
foreign keys to the same ``core.users`` table, and a DB CHECK cannot compare
two nullable-independent columns for "different users" any more robustly
than the application layer already does here).

``policy_results.evaluated_rule_keys`` is additive and nullable: historical
rows created before this column existed never recorded it and are never
backfilled with a guess.

Tables/columns changed:
    policy.policy_pack_approvals — new table
    policy.policy_results.evaluated_rule_keys — new nullable column

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "policy_results",
        sa.Column("evaluated_rule_keys", sa.JSON(), nullable=True),
        schema="policy",
    )

    op.create_table(
        "policy_pack_approvals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("policy_pack_id", sa.UUID(), nullable=False),
        sa.Column("requested_by_user_id", sa.UUID(), nullable=False),
        sa.Column("decided_by_user_id", sa.UUID(), nullable=True),
        sa.Column("decision", sa.String(20), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["policy_pack_id"],
            ["policy.policy_packs.id"],
            name=op.f("fk_policy_pack_approvals_policy_pack_id_policy_packs"),
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["core.users.id"],
            name=op.f("fk_policy_pack_approvals_requested_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_user_id"],
            ["core.users.id"],
            name=op.f("fk_policy_pack_approvals_decided_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_pack_approvals")),
        schema="policy",
    )
    op.create_index(
        op.f("ix_policy_policy_pack_approvals_policy_pack_id"),
        "policy_pack_approvals",
        ["policy_pack_id"],
        unique=False,
        schema="policy",
    )
    op.create_index(
        op.f("ix_policy_policy_pack_approvals_decision"),
        "policy_pack_approvals",
        ["decision"],
        unique=False,
        schema="policy",
    )


def downgrade() -> None:
    # destructive-migration-approved
    op.drop_table("policy_pack_approvals", schema="policy")
    op.drop_column("policy_results", "evaluated_rule_keys", schema="policy")
