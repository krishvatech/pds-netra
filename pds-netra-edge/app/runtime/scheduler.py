"""
Simple scheduler for periodic tasks such as health heartbeats.

This module contains a ``Scheduler`` class that spawns a background
thread to periodically send health messages to the MQTT broker. Future
periodic tasks (e.g. configuration refresh) can be added here.
"""

from __future__ import annotations

import threading
import logging
import time
import datetime
from typing import Optional, Dict

from ..models.event import HealthModel
from ..events.mqtt_client import MQTTClient
from ..config import Settings
import uuid
from ..config import HealthConfig
from .camera_loop import CameraHealthState


class Scheduler:
    """Periodically executes tasks such as health heartbeats and offline detection."""

    def __init__(
        self,
        settings: Settings,
        mqtt_client: MQTTClient,
        camera_states: Optional[Dict[str, 'CameraHealthState']] = None,
        interval: int = 30,
    ) -> None:
        """
        Initialize the scheduler.

        Parameters
        ----------
        settings: Settings
            Application settings loaded from YAML.
        mqtt_client: MQTTClient
            Connected MQTT client used to publish health and tamper events.
        camera_states: Optional[Dict[str, CameraHealthState]]
            Mapping of camera IDs to their mutable health state. If provided,
            the scheduler will use this to compute per-camera status and offline
            events. If None, all cameras are assumed online.
        interval: int
            Interval in seconds between health heartbeats.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.settings = settings
        self.mqtt_client = mqtt_client
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # Shared camera state from camera loops
        self.camera_states = camera_states or {}

    def start(self) -> None:
        """Start the scheduler thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="Scheduler", daemon=True)
        self._thread.start()
        self.logger.info("Scheduler started with interval=%ss", self.interval)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._send_health()
            except Exception as exc:
                self.logger.exception("Error during scheduled task: %s", exc)
            self._stop_event.wait(timeout=self.interval)

    def _send_health(self) -> None:
        """Compute and publish a health heartbeat message."""
        now_dt = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        now_iso = now_dt.replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        total_cameras = len(self.settings.cameras)
        online_cameras = total_cameras
        camera_status_list = []
        device_status = "OK"

        # Build a lookup for camera health configuration
        health_configs: Dict[str, HealthConfig] = {}
        for cam in self.settings.cameras:
            if cam.health is not None:
                health_configs[cam.id] = cam.health
            else:
                health_configs[cam.id] = HealthConfig()

        # Iterate through camera states if available
        if self.camera_states:
            online_cameras = 0
            for cam_id, state in self.camera_states.items():
                cfg = health_configs.get(cam_id, HealthConfig())
                # Determine if camera is considered online based on last frame timestamp
                online = False
                last_frame_iso: Optional[str] = None
                if state.last_frame_utc is not None:
                    last_frame_iso = state.last_frame_utc.replace(microsecond=0).isoformat().replace('+00:00', 'Z')
                    time_since = (now_dt - state.last_frame_utc).total_seconds()
                    if time_since <= cfg.no_frame_timeout_seconds:
                        online = True
                # If status has transitioned from online to offline, emit offline event
                if state.is_online and not online:
                    # Camera went offline
                    try:
                        from ..models.event import EventModel, MetaModel  # local import to avoid cycle
                        event = EventModel(
                            godown_id=self.settings.godown_id,
                            camera_id=cam_id,
                            event_id=str(uuid.uuid4()),
                            event_type="CAMERA_OFFLINE",
                            severity="critical",
                            timestamp_utc=now_iso,
                            bbox=[],
                            track_id=-1,
                            image_url=None,
                            clip_url=None,
                            meta=MetaModel(
                                zone_id="",
                                rule_id="CAM_TAMPER_HEURISTIC",
                                confidence=1.0,
                                reason="RTSP_OFFLINE",
                                extra={},
                            ),
                        )
                        self.mqtt_client.publish_event(event)
                    except Exception:
                        self.logger.exception("Failed to publish offline event for camera %s", cam_id)
                # Update state
                state.is_online = online
                if online:
                    online_cameras += 1
                # Determine last tamper reason
                last_tamper_reason = None
                if state.last_tamper_reason:
                    last_tamper_reason = state.last_tamper_reason
                    # If tamper occurred recently (< cooldown), mark degraded
                    device_status = "DEGRADED"
                # Determine device status if offline
                if not online:
                    device_status = "DEGRADED" if online_cameras > 0 else "ERROR"
                camera_status_list.append(
                    {
                        "camera_id": cam_id,
                        "online": online,
                        "last_frame_utc": last_frame_iso,
                        "last_tamper_reason": last_tamper_reason,
                    }
                )
        # Build health model
        health = HealthModel(
            godown_id=self.settings.godown_id,
            device_id=f"PDSNETRA_EDGE_{self.settings.godown_id}",
            status=device_status,
            online_cameras=online_cameras,
            total_cameras=total_cameras,
            timestamp_utc=now_iso,
            camera_status=camera_status_list if camera_status_list else None,
        )
        self.mqtt_client.publish_health(health)

    def stop(self) -> None:
        """Stop the scheduler thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self.logger.info("Scheduler stopped")
