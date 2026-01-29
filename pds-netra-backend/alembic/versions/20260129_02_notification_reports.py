"""Add alert reports and report-capable outbox.

Revision ID: 20260129_02
Revises: 20260129_01
Create Date: 2026-01-29 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260129_02"
down_revision = "20260129_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Normalize legacy scope values if present
    try:
        op.execute("UPDATE notification_endpoints SET scope='GODOWN_MANAGER' WHERE scope='GODOWN'")
    except Exception:
        pass

    op.create_table(
        "alert_reports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("scope", sa.String(length=16), nullable=False, server_default="HQ"),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("email_html", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.add_column("notification_outbox", sa.Column("kind", sa.String(length=16), nullable=False, server_default="ALERT"))
    op.add_column("notification_outbox", sa.Column("report_id", sa.String(length=36), nullable=True))
    op.create_index("ix_notification_outbox_report_id", "notification_outbox", ["report_id"])
    op.create_foreign_key(
        "fk_notification_outbox_report_id",
        "notification_outbox",
        "alert_reports",
        ["report_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("notification_outbox", "alert_id", existing_type=sa.String(length=36), nullable=True)
    op.create_unique_constraint(
        "uq_notification_outbox_report_channel_target",
        "notification_outbox",
        ["report_id", "channel", "target"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_notification_outbox_report_channel_target", "notification_outbox", type_="unique")
    op.drop_constraint("fk_notification_outbox_report_id", "notification_outbox", type_="foreignkey")
    op.drop_index("ix_notification_outbox_report_id", table_name="notification_outbox")
    op.drop_column("notification_outbox", "report_id")
    op.drop_column("notification_outbox", "kind")
    op.alter_column("notification_outbox", "alert_id", existing_type=sa.String(length=36), nullable=False)

    op.drop_table("alert_reports")
