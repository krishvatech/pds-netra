"""Add godown_id to alert_reports.

Revision ID: 20260211_01
Revises: 20260210_01
Create Date: 2026-02-11 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260211_01"
down_revision = "20260210_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alert_reports", sa.Column("godown_id", sa.String(length=64), nullable=True))
    op.create_index("ix_alert_reports_godown_id", "alert_reports", ["godown_id"])


def downgrade() -> None:
    op.drop_index("ix_alert_reports_godown_id", table_name="alert_reports")
    op.drop_column("alert_reports", "godown_id")
