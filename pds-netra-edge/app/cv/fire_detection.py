"""
Fire detection processor using Ultralytics YOLO.
"""

from __future__ import annotations

import datetime
import logging
import time
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

from .yolo_detector import YoloDetector
from .zones import is_bbox_in_zone
from ..config import FireDetectionConfig
from ..events.mqtt_client import MQTTClient
from ..models.event import EventModel, MetaModel


class FireDetectionProcessor:
    def __init__(
        self,
        camera_id: str,
        godown_id: str,
        config: FireDetectionConfig,
        zone_polygons: dict[str, List[Tuple[int, int]]],
    ) -> None:
        self.logger = logging.getLogger(f"FireDetection-{camera_id}")
        self.camera_id = camera_id
        self.godown_id = godown_id
        self.config = config
        self.zone_polygons = zone_polygons
        self.enabled = bool(config.enabled)
        self.detector: Optional[YoloDetector] = None
        self.last_infer_mono = 0.0
        self.last_emit: Optional[datetime.datetime] = None
        self.detection_times: List[datetime.datetime] = []
        self.cooldown_seconds = max(1, int(config.cooldown_seconds))
        self.min_frames_confirm = max(1, int(config.min_frames_confirm))
        self.interval_sec = max(0.2, float(config.interval_sec))
        self.class_keywords = {c.strip().lower() for c in config.class_keywords if c.strip()}
        self.zones_enabled = bool(config.zones_enabled)
        self.save_snapshot = bool(config.save_snapshot)
        self.confirm_window_sec = max(2.0, self.min_frames_confirm * self.interval_sec + 1.0)

        if not self.enabled:
            return
        model_path = Path(config.model_path).expanduser()
        if not model_path.exists():
            self.logger.warning("Fire detection disabled: weights not found at %s", model_path)
            self.enabled = False
            return
        try:
            self.detector = YoloDetector(
                model_name=str(model_path),
                device=str(config.device or "cpu"),
                conf=float(config.conf),
                iou=float(config.iou),
            )
        except Exception as exc:
            self.logger.warning("Fire detection disabled: failed to load model (%s)", exc)
            self.enabled = False

    def _matches_class(self, class_name: str) -> bool:
        name = class_name.lower()
        if not self.class_keywords:
            return False
        return any(keyword in name for keyword in self.class_keywords)

    def _find_zone(self, bbox: List[int]) -> Optional[str]:
        if not self.zones_enabled or not self.zone_polygons:
            return None
        for zone_id, polygon in self.zone_polygons.items():
            try:
                if is_bbox_in_zone(bbox, polygon):
                    return zone_id
            except Exception:
                continue
        return None

    def _prune_detections(self, now_utc: datetime.datetime) -> None:
        cutoff = now_utc - datetime.timedelta(seconds=self.confirm_window_sec)
        self.detection_times = [ts for ts in self.detection_times if ts >= cutoff]

    def process(self, frame, now_utc: datetime.datetime, mqtt_client: MQTTClient, snapshotter=None) -> None:
        if not self.enabled or self.detector is None:
            return
        if frame is None:
            return
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=datetime.timezone.utc)
        now_mono = time.monotonic()
        if now_mono - self.last_infer_mono < self.interval_sec:
            return
        self.last_infer_mono = now_mono

        try:
            detections = self.detector.detect(frame)
        except Exception as exc:
            self.logger.warning("Fire detection failed for camera %s: %s", self.camera_id, exc)
            return

        matches: List[tuple[str, float, List[int], Optional[str]]] = []
        for class_name, confidence, bbox in detections:
            if not self._matches_class(class_name):
                continue
            zone_id = self._find_zone(bbox)
            if self.zones_enabled and self.zone_polygons and zone_id is None:
                continue
            matches.append((class_name, float(confidence), bbox, zone_id))

        if not matches:
            self._prune_detections(now_utc)
            return

        self.detection_times.append(now_utc)
        self._prune_detections(now_utc)
        if len(self.detection_times) < self.min_frames_confirm:
            return

        if self.last_emit is not None:
            if (now_utc - self.last_emit).total_seconds() < self.cooldown_seconds:
                return

        classes = list({m[0].lower() for m in matches})
        confidences = [m[1] for m in matches]
        bboxes = [m[2] for m in matches][:5]
        zone_id = next((m[3] for m in matches if m[3]), None)
        top_conf = max(confidences) if confidences else 0.0

        event_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())
        timestamp_iso = now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        snapshot_url = None
        if self.save_snapshot and snapshotter is not None:
            try:
                snapshot_url = snapshotter(frame, event_id, now_utc, bbox=bboxes[0] if bboxes else None, label="Fire")
            except Exception:
                snapshot_url = None
        local_path = None
        if snapshot_url and not snapshot_url.startswith("http"):
            local_path = snapshot_url

        extra = {
            "schema_version": "1.0",
            "correlation_id": correlation_id,
        }
        if local_path:
            extra["local_snapshot_path"] = local_path

        event = EventModel(
            godown_id=self.godown_id,
            camera_id=self.camera_id,
            event_id=event_id,
            event_type="FIRE_DETECTED",
            severity="critical",
            timestamp_utc=timestamp_iso,
            bbox=bboxes[0] if bboxes else None,
            track_id=0,
            image_url=snapshot_url,
            clip_url=None,
            meta=MetaModel(
                zone_id=zone_id,
                rule_id="FIRE_DETECTED",
                confidence=top_conf,
                fire_classes=classes,
                fire_confidence=top_conf,
                fire_bboxes=bboxes,
                fire_model_name="yolo26",
                fire_model_version=None,
                fire_weights_id=Path(self.config.model_path).name,
                extra=extra,
            ),
        )
        mqtt_client.publish_event(event)
        self.last_emit = now_utc
        self.detection_times.clear()
        self.logger.warning(
            "Fire detected camera=%s godown=%s conf=%.3f classes=%s event=%s",
            self.camera_id,
            self.godown_id,
            top_conf,
            classes,
            event_id,
        )

