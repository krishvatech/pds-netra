"""add app_users and godown ownership

Revision ID: 20260210_01
Revises: 20260206_01
Create Date: 2026-02-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260210_01"
down_revision = "20260206_01"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in set(inspector.get_table_names())


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return False
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return False
    return index_name in {idx["name"] for idx in inspector.get_indexes(table_name)}


def _fk_exists(table_name: str, fk_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return False
    return fk_name in {fk.get("name") for fk in inspector.get_foreign_keys(table_name)}


def upgrade() -> None:
    if not _table_exists("app_users"):
        op.create_table(
            "app_users",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("username", sa.String(length=128), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=64), nullable=False, server_default="USER"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("username", name="uq_app_users_username"),
        )
    if not _index_exists("app_users", "ix_app_users_id"):
        op.create_index("ix_app_users_id", "app_users", ["id"], unique=False)
    if not _index_exists("app_users", "ix_app_users_username"):
        op.create_index("ix_app_users_username", "app_users", ["username"], unique=False)

    if not _column_exists("godowns", "created_by_user_id"):
        op.add_column("godowns", sa.Column("created_by_user_id", sa.String(length=36), nullable=True))
    if not _index_exists("godowns", "ix_godowns_created_by_user_id"):
        op.create_index("ix_godowns_created_by_user_id", "godowns", ["created_by_user_id"], unique=False)
    if not _fk_exists("godowns", "fk_godowns_created_by_user_id_app_users"):
        op.create_foreign_key(
            "fk_godowns_created_by_user_id_app_users",
            "godowns",
            "app_users",
            ["created_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    if _fk_exists("godowns", "fk_godowns_created_by_user_id_app_users"):
        op.drop_constraint("fk_godowns_created_by_user_id_app_users", "godowns", type_="foreignkey")
    if _index_exists("godowns", "ix_godowns_created_by_user_id"):
        op.drop_index("ix_godowns_created_by_user_id", table_name="godowns")
    if _column_exists("godowns", "created_by_user_id"):
        op.drop_column("godowns", "created_by_user_id")

    if _index_exists("app_users", "ix_app_users_username"):
        op.drop_index("ix_app_users_username", table_name="app_users")
    if _index_exists("app_users", "ix_app_users_id"):
        op.drop_index("ix_app_users_id", table_name="app_users")
    if _table_exists("app_users"):
        op.drop_table("app_users")
