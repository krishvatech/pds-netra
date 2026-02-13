"""Create database tables for PDS Netra backend."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from app.core.db import engine
from app.models import Base


logger = logging.getLogger("scripts.create_db")


def _apply_lightweight_migrations() -> None:
    """Apply small compatibility migrations used by the app startup."""
    try:
        inspector = inspect(engine)
        if "cameras" in inspector.get_table_names():
            cols = {col["name"] for col in inspector.get_columns("cameras")}
            with engine.begin() as conn:
                if "rtsp_url" not in cols:
                    conn.execute(text("ALTER TABLE cameras ADD COLUMN rtsp_url VARCHAR(512)"))
                if "is_active" not in cols:
                    conn.execute(text("ALTER TABLE cameras ADD COLUMN is_active BOOLEAN DEFAULT TRUE"))
                if "modules_json" not in cols:
                    conn.execute(text("ALTER TABLE cameras ADD COLUMN modules_json TEXT"))
                if "source_type" not in cols:
                    conn.execute(text("ALTER TABLE cameras ADD COLUMN source_type VARCHAR(16)"))
                if "source_path" not in cols:
                    conn.execute(text("ALTER TABLE cameras ADD COLUMN source_path VARCHAR(1024)"))
                if "source_run_id" not in cols:
                    conn.execute(text("ALTER TABLE cameras ADD COLUMN source_run_id VARCHAR(64)"))
    except Exception as exc:
        logger.warning("Lightweight migrations failed: %s", exc)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations()
    logger.info("Database tables created/verified.")


if __name__ == "__main__":
    main()
