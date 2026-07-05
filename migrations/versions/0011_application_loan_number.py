"""Add loan_number column to core.applications.

Adds a real ``loan_number`` column, distinct from ``los_reference``. Spec 002
(Underwriter Workspace) treats Loan Number as one of three mandatory, equally-
weighted application identifiers (borrower name, loan number, LOS reference) —
it is not interchangeable with the upstream LOS reference and must be stored
as its own column. Nullable: a MIL application record can exist before a loan
number has been assigned upstream, mirroring ``los_reference``'s nullability.

Tables altered:
    core.applications

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("loan_number", sa.String(255), nullable=True),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("applications", "loan_number", schema="core")
