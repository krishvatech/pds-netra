"""add zones table for camera polygon definitions

Revision ID: 20260302_01
Revises: 20260211_01
Create Date: 2026-03-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260302_01"
down_revision = "20260211_01"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _table_exists("zones"):
        op.create_table(
            "zones",
            sa.Column("id", sa.String(64), nullable=False),
            sa.Column("godown_id", sa.String(64), nullable=False),
            sa.Column("camera_id", sa.String(64), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("polygon", sa.JSON(), nullable=False),
            sa.Column("pixels_per_meter", sa.Float(), nullable=False, server_default="120.0"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_zones_camera_id"), "zones", ["camera_id"], unique=False)
        op.create_index(op.f("ix_zones_enabled"), "zones", ["enabled"], unique=False)
        op.create_index(op.f("ix_zones_godown_id"), "zones", ["godown_id"], unique=False)


def downgrade() -> None:
    if _table_exists("zones"):
        op.drop_index(op.f("ix_zones_enabled"), table_name="zones")
        op.drop_index(op.f("ix_zones_camera_id"), table_name="zones")
        op.drop_index(op.f("ix_zones_godown_id"), table_name="zones")
        op.drop_table("zones")
