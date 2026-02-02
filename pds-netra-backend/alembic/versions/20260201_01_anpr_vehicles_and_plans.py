"""ANPR vehicles and daily plans

Revision ID: 20260201_01
Revises: 20260130_01
Create Date: 2026-02-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260201_01"
down_revision = "20260130_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "anpr_vehicles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("godown_id", sa.String(length=64), nullable=False),
        sa.Column("plate_raw", sa.String(length=64), nullable=False),
        sa.Column("plate_norm", sa.String(length=64), nullable=False),
        sa.Column("transporter", sa.String(length=128), nullable=True),
        sa.Column("notes", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_anpr_vehicles_godown_plate", "anpr_vehicles", ["godown_id", "plate_norm"], unique=True)
    op.create_index("ix_anpr_vehicles_godown_active", "anpr_vehicles", ["godown_id", "is_active"])

    op.create_table(
        "anpr_daily_plans",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("godown_id", sa.String(length=64), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("timezone_name", sa.String(length=64), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("expected_count", sa.Integer(), nullable=True),
        sa.Column("cutoff_time_local", sa.Time(), nullable=False, server_default="18:00:00"),
        sa.Column("notes", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_anpr_daily_plans_godown_date", "anpr_daily_plans", ["godown_id", "plan_date"], unique=True)

    op.create_table(
        "anpr_daily_plan_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("plan_id", sa.String(length=36), sa.ForeignKey("anpr_daily_plans.id"), nullable=False),
        sa.Column("vehicle_id", sa.String(length=36), sa.ForeignKey("anpr_vehicles.id"), nullable=True),
        sa.Column("plate_raw", sa.String(length=64), nullable=False),
        sa.Column("plate_norm", sa.String(length=64), nullable=False),
        sa.Column("expected_by_local", sa.Time(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=True),
        sa.Column("notes", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_anpr_daily_plan_items_plan_plate", "anpr_daily_plan_items", ["plan_id", "plate_norm"], unique=True)
    op.create_index("ix_anpr_daily_plan_items_plate", "anpr_daily_plan_items", ["plate_norm"])


def downgrade() -> None:
    op.drop_index("ix_anpr_daily_plan_items_plate", table_name="anpr_daily_plan_items")
    op.drop_index("ix_anpr_daily_plan_items_plan_plate", table_name="anpr_daily_plan_items")
    op.drop_table("anpr_daily_plan_items")

    op.drop_index("ix_anpr_daily_plans_godown_date", table_name="anpr_daily_plans")
    op.drop_table("anpr_daily_plans")

    op.drop_index("ix_anpr_vehicles_godown_active", table_name="anpr_vehicles")
    op.drop_index("ix_anpr_vehicles_godown_plate", table_name="anpr_vehicles")
    op.drop_table("anpr_vehicles")

