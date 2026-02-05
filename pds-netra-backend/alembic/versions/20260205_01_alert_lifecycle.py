"""add incident lifecycle timestamps to alerts

Revision ID: 20260205_01
Revises: 20260202_01
Create Date: 2026-02-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260205_01"
down_revision = "20260202_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "alerts",
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("last_detection_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("last_whatsapp_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("last_call_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("last_email_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("alerts", "last_email_at")
    op.drop_column("alerts", "last_call_at")
    op.drop_column("alerts", "last_whatsapp_at")
    op.drop_column("alerts", "closed_at")
    op.drop_column("alerts", "last_detection_at")
    op.drop_column("alerts", "first_detected_at")
