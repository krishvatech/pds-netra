"""Seed demo data for PDS Netra backend."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from app.core.db import SessionLocal
from app.services.seed import seed_godowns, seed_cameras_from_edge_config
from app.services.rule_seed import seed_rules


logger = logging.getLogger("scripts.seed_demo_data")


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    seed_godowns_path = os.getenv("SEED_GODOWNS_PATH")
    if seed_godowns_path:
        godowns_path = Path(seed_godowns_path)
    else:
        godowns_path = Path(__file__).resolve().parents[1] / "data" / "seed_godowns.json"

    edge_config_path = os.getenv("EDGE_CONFIG_PATH")
    if edge_config_path:
        cameras_path = Path(edge_config_path)
    else:
        cameras_path = Path(__file__).resolve().parents[3] / "pds-netra-edge" / "config" / "pds_netra_config.yaml"

    with SessionLocal() as db:
        try:
            seed_godowns(db, godowns_path)
        except Exception as exc:
            logger.warning("Seed godowns failed: %s", exc)
        try:
            seed_cameras_from_edge_config(db, cameras_path)
        except Exception as exc:
            logger.warning("Seed cameras failed: %s", exc)
        try:
            seed_rules(db)
        except Exception as exc:
            logger.warning("Seed rules failed: %s", exc)

    logger.info("Demo seed complete.")


if __name__ == "__main__":
    main()
