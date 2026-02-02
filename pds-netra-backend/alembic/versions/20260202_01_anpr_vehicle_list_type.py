"""add list_type to anpr_vehicles

Revision ID: 20260202_01
Revises: 20260201_01
Create Date: 2026-02-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260202_01"
down_revision = "20260201_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "anpr_vehicles",
        sa.Column("list_type", sa.String(length=16), nullable=False, server_default="WHITELIST"),
    )


def downgrade() -> None:
    op.drop_column("anpr_vehicles", "list_type")
