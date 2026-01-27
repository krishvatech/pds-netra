"""create alert_actions table

Revision ID: 20260126_02
Revises: 20260126_01
Create Date: 2026-01-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260126_02"
down_revision = "20260126_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_actions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("alert_id", sa.Integer(), sa.ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=True),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_alert_actions_alert_id", "alert_actions", ["alert_id"])
    op.create_index("ix_alert_actions_action_type", "alert_actions", ["action_type"])


def downgrade() -> None:
    op.drop_index("ix_alert_actions_action_type", table_name="alert_actions")
    op.drop_index("ix_alert_actions_alert_id", table_name="alert_actions")
    op.drop_table("alert_actions")
