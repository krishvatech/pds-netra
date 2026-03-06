"""create rules table

Revision ID: 20260307_02
Revises: 20260307_01
Create Date: 2026-03-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260307_02"
down_revision: Union[str, Sequence[str], None] = "20260307_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("rule_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["zone_id"], ["zone.id"]),
        sa.ForeignKeyConstraint(["rule_type_id"], ["rule_type.id"]),
    )
    op.create_index("ix_rules_zone_id", "rules", ["zone_id"])
    op.create_index("ix_rules_rule_type_id", "rules", ["rule_type_id"])


def downgrade() -> None:
    op.drop_index("ix_rules_rule_type_id", table_name="rules")
    op.drop_index("ix_rules_zone_id", table_name="rules")
    op.drop_table("rules")
