"""add line crossing name column for cameras

Revision ID: 20260305_02
Revises: 20260305_01
Create Date: 2026-03-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260305_02"
down_revision = "20260305_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cameras", sa.Column("line_cross_name", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("cameras", "line_cross_name")
