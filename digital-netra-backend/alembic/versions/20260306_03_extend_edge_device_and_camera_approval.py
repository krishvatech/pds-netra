"""extend edge_device fields and add camera approval status

Revision ID: 20260306_03
Revises: 20260306_02
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260306_03"
down_revision: Union[str, Sequence[str], None] = "20260306_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("edge_device"):
        cols = _column_names(inspector, "edge_device")
        if "location" not in cols:
            op.add_column("edge_device", sa.Column("location", sa.String(length=255), nullable=True))
        if "ip" not in cols:
            op.add_column("edge_device", sa.Column("ip", sa.String(length=64), nullable=True))
        if "password" not in cols:
            op.add_column("edge_device", sa.Column("password", sa.String(length=255), nullable=True))
        if "user_id" not in cols:
            op.add_column("edge_device", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
            op.create_foreign_key("fk_edge_device_user_id", "edge_device", "app_user", ["user_id"], ["id"])
            op.create_index("ix_edge_device_user_id", "edge_device", ["user_id"])
        if "updated_at" not in cols:
            op.add_column(
                "edge_device",
                sa.Column(
                    "updated_at",
                    sa.DateTime(timezone=True),
                    nullable=False,
                    server_default=sa.text("now()"),
                ),
            )

    if inspector.has_table("camera"):
        cols = _column_names(inspector, "camera")
        if "approval_status" not in cols:
            op.add_column(
                "camera",
                sa.Column(
                    "approval_status",
                    sa.String(length=32),
                    nullable=False,
                    server_default=sa.text("'pending'"),
                ),
            )
            op.execute(sa.text("UPDATE camera SET approval_status = 'approved'"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("camera"):
        cols = _column_names(inspector, "camera")
        if "approval_status" in cols:
            op.drop_column("camera", "approval_status")

    if inspector.has_table("edge_device"):
        cols = _column_names(inspector, "edge_device")
        if "updated_at" in cols:
            op.drop_column("edge_device", "updated_at")
        if "user_id" in cols:
            op.drop_index("ix_edge_device_user_id", table_name="edge_device")
            op.drop_constraint("fk_edge_device_user_id", "edge_device", type_="foreignkey")
            op.drop_column("edge_device", "user_id")
        if "password" in cols:
            op.drop_column("edge_device", "password")
        if "ip" in cols:
            op.drop_column("edge_device", "ip")
        if "location" in cols:
            op.drop_column("edge_device", "location")
