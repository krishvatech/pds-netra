"""create rule_type table

Revision ID: 20260306_02
Revises: 20260306_01
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260306_02"
down_revision: Union[str, Sequence[str], None] = "20260306_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("rule_type"):
        return

    op.create_table(
        "rule_type",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("rule_type_name", sa.String(length=128), nullable=False),
        sa.Column("rule_type_slug", sa.String(length=128), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
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
    op.create_index("ix_rule_type_slug", "rule_type", ["rule_type_slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_rule_type_slug", table_name="rule_type")
    op.drop_table("rule_type")
