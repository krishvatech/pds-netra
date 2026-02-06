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


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _column_exists("alerts", "first_detected_at"):
        op.add_column(
            "alerts",
            sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _column_exists("alerts", "last_detection_at"):
        op.add_column(
            "alerts",
            sa.Column("last_detection_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _column_exists("alerts", "closed_at"):
        op.add_column(
            "alerts",
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _column_exists("alerts", "last_whatsapp_at"):
        op.add_column(
            "alerts",
            sa.Column("last_whatsapp_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _column_exists("alerts", "last_call_at"):
        op.add_column(
            "alerts",
            sa.Column("last_call_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _column_exists("alerts", "last_email_at"):
        op.add_column(
            "alerts",
            sa.Column("last_email_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("alerts", "last_email_at"):
        op.drop_column("alerts", "last_email_at")
    if _column_exists("alerts", "last_call_at"):
        op.drop_column("alerts", "last_call_at")
    if _column_exists("alerts", "last_whatsapp_at"):
        op.drop_column("alerts", "last_whatsapp_at")
    if _column_exists("alerts", "closed_at"):
        op.drop_column("alerts", "closed_at")
    if _column_exists("alerts", "last_detection_at"):
        op.drop_column("alerts", "last_detection_at")
    if _column_exists("alerts", "first_detected_at"):
        op.drop_column("alerts", "first_detected_at")
