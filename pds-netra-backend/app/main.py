"""
Entry point for the PDS Netra backend.

This script creates the FastAPI application, includes all API routers,
and sets up middleware such as CORS if needed. Run with:

    uvicorn app.main:app --reload

"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os
from pathlib import Path

from .core.db import engine, SessionLocal
from .models import Base
from .services.seed import seed_godowns, seed_cameras_from_edge_config
from .services.mqtt_consumer import MQTTConsumer

from .api import api_router
from .core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="PDS Netra Backend", version="0.1.0")
    # Include API routers
    app.include_router(api_router)
    media_root = Path(__file__).resolve().parents[1] / "data" / "snapshots"
    annotated_root = Path(__file__).resolve().parents[1] / "data" / "annotated"
    live_root = Path(__file__).resolve().parents[1] / "data" / "live"
    app.mount("/media/snapshots", StaticFiles(directory=media_root, check_dir=False), name="snapshots")
    app.mount("/media/annotated", StaticFiles(directory=annotated_root, check_dir=False), name="annotated")
    app.mount("/media/live", StaticFiles(directory=live_root, check_dir=False), name="live")
    app.state.mqtt_consumer = None
    # Ensure tables exist for PoC/local use
    @app.on_event("startup")
    def _init_db() -> None:
        media_root.mkdir(parents=True, exist_ok=True)
        annotated_root.mkdir(parents=True, exist_ok=True)
        live_root.mkdir(parents=True, exist_ok=True)
        if os.getenv("AUTO_CREATE_DB", "true").lower() in {"1", "true", "yes"}:
            Base.metadata.create_all(bind=engine)
        if os.getenv("AUTO_SEED_GODOWNS", "true").lower() in {"1", "true", "yes"}:
            seed_path = os.getenv("SEED_GODOWNS_PATH", "")
            if seed_path:
                path = Path(seed_path)
            else:
                path = Path(__file__).resolve().parents[1] / "data" / "seed_godowns.json"
            try:
                with SessionLocal() as db:
                    seed_godowns(db, path)
            except Exception:
                pass
        if os.getenv("AUTO_SEED_CAMERAS_FROM_EDGE", "true").lower() in {"1", "true", "yes"}:
            edge_path = os.getenv("EDGE_CONFIG_PATH", "")
            if edge_path:
                path = Path(edge_path)
            else:
                path = Path(__file__).resolve().parents[3] / "pds-netra-edge" / "config" / "pds_netra_config.yaml"
            try:
                with SessionLocal() as db:
                    seed_cameras_from_edge_config(db, path)
            except Exception:
                pass
        if os.getenv("ENABLE_MQTT_CONSUMER", "true").lower() in {"1", "true", "yes"}:
            consumer = MQTTConsumer()
            consumer.start()
            app.state.mqtt_consumer = consumer
    @app.on_event("shutdown")
    def _shutdown() -> None:
        consumer = getattr(app.state, "mqtt_consumer", None)
        if consumer:
            consumer.stop()
    return app


app = create_app()
