"""create rules table

Revision ID: 20260126_01
Revises: 
Create Date: 2026-01-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260126_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("godown_id", sa.String(length=64), nullable=False),
        sa.Column("camera_id", sa.String(length=64), nullable=False),
        sa.Column("zone_id", sa.String(length=64), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("params", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_rules_godown_id", "rules", ["godown_id"])
    op.create_index("ix_rules_camera_id", "rules", ["camera_id"])
    op.create_index("ix_rules_zone_id", "rules", ["zone_id"])
    op.create_index("ix_rules_type", "rules", ["type"])
    op.create_index("ix_rules_enabled", "rules", ["enabled"])


def downgrade() -> None:
    op.drop_index("ix_rules_enabled", table_name="rules")
    op.drop_index("ix_rules_type", table_name="rules")
    op.drop_index("ix_rules_zone_id", table_name="rules")
    op.drop_index("ix_rules_camera_id", table_name="rules")
    op.drop_index("ix_rules_godown_id", table_name="rules")
    op.drop_table("rules")
