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
from sqlalchemy import create_engine, inspect


LEGACY_BASELINE_REVISION = "20260202_01"


def _build_alembic_config() -> Config:
    backend_root = Path(__file__).resolve().parents[2]
    alembic_ini = backend_root / "alembic.ini"
    if not alembic_ini.exists():
        raise FileNotFoundError(f"alembic.ini not found at {alembic_ini}")
    cfg = Config(str(alembic_ini))
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _needs_legacy_bootstrap(cfg: Config) -> bool:
    db_url = cfg.get_main_option("sqlalchemy.url")
    if not db_url:
        return False
    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "alembic_version" in tables:
        return False
    # Legacy local DBs were built via SQLAlchemy create_all() without Alembic state.
    return any(name in tables for name in {"alerts", "rules", "godowns", "cameras"})


def run_migrations_to_head() -> None:
    cfg = _build_alembic_config()
    if _needs_legacy_bootstrap(cfg):
        command.stamp(cfg, LEGACY_BASELINE_REVISION)
    command.upgrade(cfg, "head")


def main() -> int:
    try:
        run_migrations_to_head()
    except Exception as exc:
        print(exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
