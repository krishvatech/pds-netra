"""vehicle gate sessions

Revision ID: 20260128_04
Revises: 20260128_03
Create Date: 2026-01-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260128_04"
down_revision = "20260128_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vehicle_gate_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("godown_id", sa.String(length=64), nullable=False),
        sa.Column("anpr_camera_id", sa.String(length=64), nullable=True),
        sa.Column("plate_raw", sa.String(length=64), nullable=False),
        sa.Column("plate_norm", sa.String(length=64), nullable=False),
        sa.Column("entry_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="OPEN"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_event_id", sa.String(length=64), nullable=True),
        sa.Column("exit_event_id", sa.String(length=64), nullable=True),
        sa.Column("reminders_sent", sa.JSON(), nullable=True),
        sa.Column("last_snapshot_url", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_vehicle_gate_sessions_godown_plate_status",
        "vehicle_gate_sessions",
        ["godown_id", "plate_norm", "status"],
    )
    op.create_index(
        "ix_vehicle_gate_sessions_status_entry",
        "vehicle_gate_sessions",
        ["status", "entry_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_vehicle_gate_sessions_status_entry", table_name="vehicle_gate_sessions")
    op.drop_index("ix_vehicle_gate_sessions_godown_plate_status", table_name="vehicle_gate_sessions")
    op.drop_table("vehicle_gate_sessions")
