"""
Run Alembic migrations to head.

Usage:
    python -m app.scripts.run_migrations
"""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config


def main() -> int:
    backend_root = Path(__file__).resolve().parents[2]
    alembic_ini = backend_root / "alembic.ini"
    if not alembic_ini.exists():
        print(f"alembic.ini not found at {alembic_ini}")
        return 1
    cfg = Config(str(alembic_ini))
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
