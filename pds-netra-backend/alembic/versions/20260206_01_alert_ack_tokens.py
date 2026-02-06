"""add alert acknowledgement token fields

Revision ID: 20260206_01
Revises: 20260205_01
Create Date: 2026-02-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260206_01"
down_revision = "20260205_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "alerts",
        sa.Column("ack_token_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("ack_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("ack_token_used_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("alerts", "ack_token_used_at")
    op.drop_column("alerts", "ack_token_expires_at")
    op.drop_column("alerts", "ack_token_hash")
