"""create zone table

Revision ID: 20260307_01
Revises: 20260306_04
Create Date: 2026-03-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260307_01"
down_revision: Union[str, Sequence[str], None] = "20260306_04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "zone",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("zone_name", sa.String(length=255), nullable=False),
        sa.Column("polygon", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["camera_id"], ["camera.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_zone_camera_id", "zone", ["camera_id"])


def downgrade() -> None:
    op.drop_index("ix_zone_camera_id", table_name="zone")
    op.drop_table("zone")
