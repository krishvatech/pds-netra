"""create app_user_rule_type table

Revision ID: 20260306_04
Revises: 20260306_03
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260306_04"
down_revision: Union[str, Sequence[str], None] = "20260306_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("app_user_rule_type"):
        return

    op.create_table(
        "app_user_rule_type",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("rule_type_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rule_type.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_app_user_rule_type_user_id", "app_user_rule_type", ["user_id"])
    op.create_index("ix_app_user_rule_type_rule_type_id", "app_user_rule_type", ["rule_type_id"])
    op.create_index(
        "uq_app_user_rule_type_user_id_rule_type_id",
        "app_user_rule_type",
        ["user_id", "rule_type_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_app_user_rule_type_user_id_rule_type_id", table_name="app_user_rule_type")
    op.drop_index("ix_app_user_rule_type_rule_type_id", table_name="app_user_rule_type")
    op.drop_index("ix_app_user_rule_type_user_id", table_name="app_user_rule_type")
    op.drop_table("app_user_rule_type")
