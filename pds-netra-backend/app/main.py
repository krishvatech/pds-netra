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
import threading
from sqlalchemy import inspect, text

from .core.db import engine, SessionLocal
from .models import Base
from .models.dispatch_issue import DispatchIssue
from .services.seed import seed_godowns, seed_cameras_from_edge_config
from .services.rule_seed import seed_rules
from .services.mqtt_consumer import MQTTConsumer
from .services.dispatch_watchdog import run_dispatch_watchdog
from .services.dispatch_plan_sync import run_dispatch_plan_sync

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
    app.state.dispatch_watchdog_stop = None
    app.state.dispatch_watchdog_thread = None
    app.state.dispatch_plan_sync_stop = None
    app.state.dispatch_plan_sync_thread = None
    # Ensure tables exist for PoC/local use
    @app.on_event("startup")
    def _init_db() -> None:
        media_root.mkdir(parents=True, exist_ok=True)
        annotated_root.mkdir(parents=True, exist_ok=True)
        live_root.mkdir(parents=True, exist_ok=True)
        if os.getenv("AUTO_CREATE_DB", "true").lower() in {"1", "true", "yes"}:
            Base.metadata.create_all(bind=engine)
        try:
            inspector = inspect(engine)
            if "cameras" in inspector.get_table_names():
                cols = {col["name"] for col in inspector.get_columns("cameras")}
                with engine.begin() as conn:
                    if "rtsp_url" not in cols:
                        conn.execute(text("ALTER TABLE cameras ADD COLUMN rtsp_url VARCHAR(512)"))
                    if "is_active" not in cols:
                        conn.execute(text("ALTER TABLE cameras ADD COLUMN is_active BOOLEAN DEFAULT TRUE"))
        except Exception:
            pass
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
        if os.getenv("AUTO_SEED_RULES", "true").lower() in {"1", "true", "yes"}:
            try:
                with SessionLocal() as db:
                    seed_rules(db)
            except Exception:
                pass
        if os.getenv("ENABLE_MQTT_CONSUMER", "true").lower() in {"1", "true", "yes"}:
            consumer = MQTTConsumer()
            consumer.start()
            app.state.mqtt_consumer = consumer
        if os.getenv("ENABLE_DISPATCH_WATCHDOG", "true").lower() in {"1", "true", "yes"}:
            stop_event = threading.Event()
            thread = threading.Thread(
                target=run_dispatch_watchdog,
                args=(stop_event,),
                daemon=True,
                name="dispatch-watchdog",
            )
            thread.start()
            app.state.dispatch_watchdog_stop = stop_event
            app.state.dispatch_watchdog_thread = thread
        if os.getenv("ENABLE_DISPATCH_PLAN_SYNC", "true").lower() in {"1", "true", "yes"}:
            stop_event = threading.Event()
            thread = threading.Thread(
                target=run_dispatch_plan_sync,
                args=(stop_event,),
                daemon=True,
                name="dispatch-plan-sync",
            )
            thread.start()
            app.state.dispatch_plan_sync_stop = stop_event
            app.state.dispatch_plan_sync_thread = thread
    @app.on_event("shutdown")
    def _shutdown() -> None:
        consumer = getattr(app.state, "mqtt_consumer", None)
        if consumer:
            consumer.stop()
        stop_event = getattr(app.state, "dispatch_watchdog_stop", None)
        if stop_event:
            stop_event.set()
        thread = getattr(app.state, "dispatch_watchdog_thread", None)
        if thread:
            thread.join(timeout=5)
        stop_event = getattr(app.state, "dispatch_plan_sync_stop", None)
        if stop_event:
            stop_event.set()
        thread = getattr(app.state, "dispatch_plan_sync_thread", None)
        if thread:
            thread.join(timeout=5)
    return app


app = create_app()
