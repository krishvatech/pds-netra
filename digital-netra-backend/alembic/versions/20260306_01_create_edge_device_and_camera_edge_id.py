"""create edge_device table and camera.edge_id

Revision ID: 20260306_01
Revises: 20260305_03
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260306_01"
down_revision: Union[str, Sequence[str], None] = "20260305_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("edge_device"):
        op.create_table(
            "edge_device",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("api_key", sa.String(length=255), nullable=False, unique=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )
        op.create_index("ix_edge_device_api_key", "edge_device", ["api_key"], unique=True)

    if "edge_id" not in [col["name"] for col in inspector.get_columns("camera")]:
        op.add_column("camera", sa.Column("edge_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key("fk_camera_edge_id", "camera", "edge_device", ["edge_id"], ["id"])
        op.create_index("ix_camera_edge_id", "camera", ["edge_id"])


def downgrade() -> None:
    op.drop_index("ix_camera_edge_id", table_name="camera")
    op.drop_constraint("fk_camera_edge_id", "camera", type_="foreignkey")
    op.drop_column("camera", "edge_id")

    op.drop_index("ix_edge_device_api_key", table_name="edge_device")
    op.drop_table("edge_device")
