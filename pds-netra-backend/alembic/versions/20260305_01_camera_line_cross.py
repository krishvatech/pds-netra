"""add line crossing columns for cameras

Revision ID: 20260305_01
Revises: 20260302_01
Create Date: 2026-03-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260305_01"
down_revision = "20260302_01"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("cameras", sa.Column("line_cross_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("cameras", sa.Column("line_cross", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("cameras", "line_cross")
    op.drop_column("cameras", "line_cross_enabled")
