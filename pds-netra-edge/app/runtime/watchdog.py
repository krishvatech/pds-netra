"""
Edge watchdog for camera stall detection and health reporting.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import uuid
import threading
from pathlib import Path
from typing import Dict, Optional, Callable

from ..core.errors import safe_json_dump_atomic
from ..models.event import EventModel, MetaModel


def _read_bool(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y"}


def _read_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _read_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


class EdgeWatchdog:
    def __init__(
        self,
        *,
        settings,
        camera_states: Dict[str, object],
        restart_camera: Optional[Callable[[str], bool]],
        mqtt_client,
        outbox=None,
    ) -> None:
        self.logger = logging.getLogger("EdgeWatchdog")
        self.settings = settings
        self.camera_states = camera_states
        self.restart_camera = restart_camera
        self.mqtt_client = mqtt_client
        self.outbox = outbox
        self.interval_sec = _read_float("EDGE_WATCHDOG_INTERVAL_SEC", 5.0)
        self.stall_sec = _read_int("EDGE_WATCHDOG_CAMERA_STALL_SEC", 45)
        self.fatal_sec = _read_int("EDGE_WATCHDOG_FATAL_SEC", 180)
        self.health_path = self._resolve_health_path(
            os.getenv("EDGE_HEALTH_PATH", "/opt/app/data/edge_health.json")
        )
        self.http_enabled = _read_bool("EDGE_HEALTH_HTTP_ENABLED", "false")
        self.http_port = _read_int("EDGE_HEALTH_HTTP_PORT", 9100)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._health_lock = threading.Lock()
        self._last_health: Dict[str, object] = {}
        self._stall_since: Dict[str, datetime.datetime] = {}
        self._restart_attempted: Dict[str, datetime.datetime] = {}
        self._http_server = None
        self._http_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="EdgeWatchdog", daemon=True)
        self._thread.start()
        if self.http_enabled:
            self._start_http_server()
        self.logger.info(
            "Watchdog started interval=%ss stall=%ss fatal=%ss health=%s",
            self.interval_sec,
            self.stall_sec,
            self.fatal_sec,
            self.health_path,
        )

    def stop(self) -> None:
        self._stop.set()
        if self._http_server is not None:
            try:
                self._http_server.shutdown()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=5)
        if self._http_thread is not None:
            self._http_thread.join(timeout=5)
        self.logger.info("Watchdog stopped")

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as exc:
                self.logger.exception("Watchdog tick failed: %s", exc)
            self._stop.wait(timeout=self.interval_sec)

    def _tick(self) -> None:
        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        cameras_health = []
        mqtt_connected = False
        try:
            mqtt_connected = bool(self.mqtt_client.is_connected())
        except Exception:
            mqtt_connected = False
        outbox_stats = self.outbox.stats() if self.outbox else {}

        for cam_id, state in self.camera_states.items():
            last_frame = getattr(state, "last_frame_utc", None)
            last_event = getattr(state, "last_event_utc", None)
            suppress = bool(getattr(state, "suppress_offline_events", False))
            fps_estimate = getattr(state, "fps_estimate", None)
            last_frame_age = None
            if last_frame is not None:
                last_frame_age = (now - last_frame).total_seconds()
            elif getattr(state, "started_at_utc", None) is not None:
                last_frame_age = (now - state.started_at_utc).total_seconds()
            if not suppress:
                self._check_stall(cam_id, state, now, last_frame_age)

            cameras_health.append(
                {
                    "camera_id": cam_id,
                    "last_frame_utc": last_frame.isoformat().replace("+00:00", "Z") if last_frame else None,
                    "last_event_utc": last_event.isoformat().replace("+00:00", "Z") if last_event else None,
                    "last_frame_age_sec": int(last_frame_age) if last_frame_age is not None else None,
                    "fps_estimate": fps_estimate,
                    "suppress_offline_events": suppress,
                }
            )

        health = {
            "timestamp_utc": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "mqtt_connected": mqtt_connected,
            "outbox": outbox_stats,
            "cameras": cameras_health,
        }
        with self._health_lock:
            self._last_health = health
        safe_json_dump_atomic(self.health_path, health, logger=self.logger)

    def _check_stall(self, cam_id: str, state, now: datetime.datetime, last_frame_age: Optional[float]) -> None:
        if last_frame_age is None:
            return
        if last_frame_age <= self.stall_sec:
            if cam_id in self._stall_since:
                self.logger.info("Camera recovered from stall: %s", cam_id)
                self._stall_since.pop(cam_id, None)
                self._restart_attempted.pop(cam_id, None)
            return

        stall_since = self._stall_since.get(cam_id)
        if stall_since is None:
            self._stall_since[cam_id] = now
            self.logger.error("Camera stalled: camera=%s age_sec=%.1f", cam_id, last_frame_age)
            if not getattr(state, "offline_reported", False) and not getattr(state, "suppress_offline_events", False):
                self._emit_offline_event(cam_id, now, reason="WATCHDOG_STALL")
                state.offline_reported = True
            if self.restart_camera and cam_id not in self._restart_attempted:
                restarted = False
                try:
                    restarted = bool(self.restart_camera(cam_id))
                except Exception as exc:
                    self.logger.error("Camera restart failed camera=%s error=%s", cam_id, exc)
                self._restart_attempted[cam_id] = now
                if restarted:
                    self.logger.warning("Camera restart requested: %s", cam_id)
            return

        if (now - stall_since).total_seconds() >= self.fatal_sec:
            self.logger.critical("Fatal camera stall: camera=%s age_sec=%.1f", cam_id, last_frame_age)
            os._exit(2)

    def _emit_offline_event(self, cam_id: str, now: datetime.datetime, reason: str) -> None:
        try:
            event = EventModel(
                godown_id=self.settings.godown_id,
                camera_id=cam_id,
                event_id=str(uuid.uuid4()),
                event_type="CAMERA_OFFLINE",
                severity="critical",
                timestamp_utc=now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                bbox=None,
                track_id=None,
                image_url=None,
                clip_url=None,
                meta=MetaModel(
                    zone_id=None,
                    rule_id="EDGE_WATCHDOG",
                    confidence=1.0,
                    reason=reason,
                    extra={},
                ),
            )
            self.mqtt_client.publish_event(event)
        except Exception as exc:
            self.logger.warning("Watchdog offline event failed camera=%s error=%s", cam_id, exc)

    def _resolve_health_path(self, configured: str) -> Path:
        path = Path(configured)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        except Exception:
            fallback = Path("/tmp/edge_health.json")
            try:
                fallback.parent.mkdir(parents=True, exist_ok=True)
                self.logger.warning("Health path fallback to %s", fallback)
            except Exception:
                pass
            return fallback

    def _start_http_server(self) -> None:
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        watchdog = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # type: ignore[override]
                if self.path not in ("/health", "/healthz", "/"):
                    self.send_response(404)
                    self.end_headers()
                    return
                payload = watchdog._get_health_payload()
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # type: ignore[override]
                return

        try:
            self._http_server = ThreadingHTTPServer(("0.0.0.0", self.http_port), Handler)
            self._http_thread = threading.Thread(
                target=self._http_server.serve_forever,
                name="EdgeHealthHTTP",
                daemon=True,
            )
            self._http_thread.start()
            self.logger.info("Health HTTP server started on port %s", self.http_port)
        except Exception as exc:
            self.logger.warning("Health HTTP server failed to start: %s", exc)

    def _get_health_payload(self) -> Dict[str, object]:
        with self._health_lock:
            if self._last_health:
                return self._last_health
        return {"status": "starting"}
