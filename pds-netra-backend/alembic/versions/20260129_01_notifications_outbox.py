"""Add notification endpoints and outbox tables.

Revision ID: 20260129_01
Revises: 20260128_04
Create Date: 2026-01-29 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260129_01"
down_revision = "20260128_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_endpoints",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("godown_id", sa.String(length=64), nullable=True),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("target", sa.String(length=256), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("alert_id", sa.String(length=36), sa.ForeignKey("alerts.public_id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("target", sa.String(length=256), nullable=False),
        sa.Column("subject", sa.String(length=256), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("media_url", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("provider_message_id", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notification_outbox_alert_id", "notification_outbox", ["alert_id"])
    op.create_index("ix_notification_outbox_status_next_retry", "notification_outbox", ["status", "next_retry_at"])
    op.create_unique_constraint(
        "uq_notification_outbox_alert_channel_target",
        "notification_outbox",
        ["alert_id", "channel", "target"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_notification_outbox_alert_channel_target", "notification_outbox", type_="unique")
    op.drop_index("ix_notification_outbox_status_next_retry", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_alert_id", table_name="notification_outbox")
    op.drop_table("notification_outbox")
    op.drop_table("notification_endpoints")

