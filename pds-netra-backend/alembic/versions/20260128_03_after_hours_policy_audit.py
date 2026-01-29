"""after hours policy audit log

Revision ID: 20260128_03
Revises: 20260128_02
Create Date: 2026-01-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260128_03"
down_revision = "20260128_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "after_hours_policy_audits",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("godown_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("actor", sa.String(length=128), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="api"),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("after_hours_policy_audits")
