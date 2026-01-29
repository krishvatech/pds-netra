"""watchlist and blacklist detection tables

Revision ID: 20260128_01
Revises: 20260126_02
Create Date: 2026-01-28
"""

from __future__ import annotations

import uuid
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260128_01"
down_revision = "20260126_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watchlist_persons",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("alias", sa.String(length=256), nullable=True),
        sa.Column("reason", sa.String(length=512), nullable=True),
        sa.Column("notes", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "watchlist_person_images",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("person_id", sa.String(length=36), sa.ForeignKey("watchlist_persons.id", ondelete="CASCADE")),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("storage_path", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "watchlist_person_embeddings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("person_id", sa.String(length=36), sa.ForeignKey("watchlist_persons.id", ondelete="CASCADE")),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("embedding_version", sa.String(length=64), nullable=False, server_default="v1"),
        sa.Column("embedding_hash", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "face_match_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("godown_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("camera_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("stream_id", sa.String(length=64), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("is_blacklisted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("blacklist_person_id", sa.String(length=36), sa.ForeignKey("watchlist_persons.id"), nullable=True),
        sa.Column("snapshot_url", sa.String(length=1024), nullable=True),
        sa.Column("storage_path", sa.String(length=1024), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "notification_recipients",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("destination", sa.String(length=256), nullable=False),
        sa.Column("godown_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.add_column("alerts", sa.Column("public_id", sa.String(length=36), nullable=True))
    op.add_column("alerts", sa.Column("title", sa.String(length=256), nullable=True))
    op.add_column("alerts", sa.Column("acknowledged_by", sa.String(length=128), nullable=True))
    op.add_column("alerts", sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("alerts", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM alerts WHERE public_id IS NULL")).fetchall()
    for (alert_id,) in rows:
        conn.execute(
            sa.text("UPDATE alerts SET public_id=:pid, updated_at=:ts WHERE id=:id"),
            {
                "pid": str(uuid.uuid4()),
                "ts": datetime.utcnow(),
                "id": alert_id,
            },
        )
    op.create_index("ix_alerts_public_id", "alerts", ["public_id"], unique=True)
    op.alter_column("alerts", "public_id", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_alerts_public_id", table_name="alerts")
    op.drop_column("alerts", "updated_at")
    op.drop_column("alerts", "acknowledged_at")
    op.drop_column("alerts", "acknowledged_by")
    op.drop_column("alerts", "title")
    op.drop_column("alerts", "public_id")

    op.drop_table("notification_recipients")
    op.drop_table("face_match_events")
    op.drop_table("watchlist_person_embeddings")
    op.drop_table("watchlist_person_images")
    op.drop_table("watchlist_persons")
