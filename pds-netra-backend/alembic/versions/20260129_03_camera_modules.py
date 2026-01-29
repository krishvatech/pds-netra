"""Add camera modules JSON storage.

Revision ID: 20260129_03
Revises: 20260129_02
Create Date: 2026-01-29 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260129_03"
down_revision = "20260129_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cameras", sa.Column("modules_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("cameras", "modules_json")
