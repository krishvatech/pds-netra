"""add first_name and last_name to app_user

Revision ID: 20260305_02
Revises: 20260305_01
Create Date: 2026-03-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260305_02"
down_revision: Union[str, Sequence[str], None] = "20260305_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("first_name", sa.String(length=128), nullable=True))
    op.add_column("app_user", sa.Column("last_name", sa.String(length=128), nullable=True))

    op.execute("UPDATE app_user SET first_name = COALESCE(first_name, 'User')")
    op.execute("UPDATE app_user SET last_name = COALESCE(last_name, 'Account')")

    op.alter_column("app_user", "first_name", nullable=False)
    op.alter_column("app_user", "last_name", nullable=False)


def downgrade() -> None:
    op.drop_column("app_user", "last_name")
    op.drop_column("app_user", "first_name")
