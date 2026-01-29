"""after hours presence policies

Revision ID: 20260128_02
Revises: 20260128_01
Create Date: 2026-01-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260128_02"
down_revision = "20260128_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "after_hours_policies",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("godown_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("day_start", sa.String(length=8), nullable=False, server_default="09:00"),
        sa.Column("day_end", sa.String(length=8), nullable=False, server_default="19:00"),
        sa.Column("presence_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("after_hours_policies")
