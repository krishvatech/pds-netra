"""Make camera primary key composite (godown_id, id).

Revision ID: 20260130_01
Revises: 20260129_03
Create Date: 2026-01-30 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "20260130_01"
down_revision = "20260129_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("cameras_pkey", "cameras", type_="primary")
    op.create_primary_key("cameras_pkey", "cameras", ["godown_id", "id"])


def downgrade() -> None:
    op.drop_constraint("cameras_pkey", "cameras", type_="primary")
    op.create_primary_key("cameras_pkey", "cameras", ["id"])