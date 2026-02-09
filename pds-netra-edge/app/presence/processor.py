"""
After-hours presence processor for emitting person/vehicle presence events.
"""

from __future__ import annotations

import datetime
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional

from zoneinfo import ZoneInfo

from ..events.mqtt_client import MQTTClient
from ..schemas.presence import PresenceEvent, PresencePayload, PresenceEvidence


def _parse_time_string(value: str) -> datetime.time:
    try:
        return datetime.datetime.strptime(value, "%H:%M").time()
    except Exception:
        return datetime.time(0, 0)


def _is_time_in_range(now_time: datetime.time, start_time: datetime.time, end_time: datetime.time) -> bool:
    if start_time <= end_time:
        return start_time <= now_time < end_time
    return now_time >= start_time or now_time < end_time


@dataclass
class PresenceConfig:
    enabled: bool
    day_start: str
    day_end: str
    emit_only_after_hours: bool
    person_interval_sec: int
    vehicle_interval_sec: int
    person_cooldown_sec: int
    vehicle_cooldown_sec: int
    min_confidence: float
    person_classes: List[str]
    vehicle_classes: List[str]
    http_fallback: bool
    timezone: str


class AfterHoursPresenceProcessor:
    def __init__(self, camera_id: str, godown_id: str, config: PresenceConfig) -> None:
        self.logger = logging.getLogger(f"AfterHoursPresence-{camera_id}")
        self.camera_id = camera_id
        self.godown_id = godown_id
        self.config = config
        try:
            self.tz = ZoneInfo(config.timezone)
        except Exception:
            self.tz = ZoneInfo("UTC")
        self.person_classes = {c.strip().lower() for c in config.person_classes if c.strip()}
        self.vehicle_classes = {c.strip().lower() for c in config.vehicle_classes if c.strip()}
        self._last_person_emit: Optional[datetime.datetime] = None
        self._last_vehicle_emit: Optional[datetime.datetime] = None
        self._person_present = False
        self._vehicle_present = False
        self._last_person_sample = 0.0
        self._last_vehicle_sample = 0.0

    def _is_after_hours(self, now_utc: datetime.datetime) -> bool:
        now_local = now_utc.astimezone(self.tz).timetz()
        day_start = _parse_time_string(self.config.day_start)
        day_end = _parse_time_string(self.config.day_end)
        in_day = _is_time_in_range(now_local, day_start, day_end)
        return not in_day

    def process(
        self,
        objects: Iterable,
        now_utc: datetime.datetime,
        mqtt_client: MQTTClient,
        frame: Optional[Any] = None,
        snapshotter=None,
    ) -> None:
        if not self.config.enabled:
            return
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=datetime.timezone.utc)
        after_hours = self._is_after_hours(now_utc)
        if self.config.emit_only_after_hours and not after_hours:
            self._person_present = False
            self._vehicle_present = False
            return
        now_mono = time.monotonic()
        if now_mono - self._last_person_sample >= max(0.2, self.config.person_interval_sec):
            self._last_person_sample = now_mono
            self._maybe_emit(
                event_type="PERSON_DETECTED",
                objects=objects,
                classes=self.person_classes,
                now_utc=now_utc,
                after_hours=after_hours,
                cooldown_sec=self.config.person_cooldown_sec,
                last_emit_ref="_last_person_emit",
                present_ref="_person_present",
                mqtt_client=mqtt_client,
                frame=frame,
                snapshotter=snapshotter,
            )
        if now_mono - self._last_vehicle_sample >= max(0.2, self.config.vehicle_interval_sec):
            self._last_vehicle_sample = now_mono
            self._maybe_emit(
                event_type="VEHICLE_DETECTED",
                objects=objects,
                classes=self.vehicle_classes,
                now_utc=now_utc,
                after_hours=after_hours,
                cooldown_sec=self.config.vehicle_cooldown_sec,
                last_emit_ref="_last_vehicle_emit",
                present_ref="_vehicle_present",
                mqtt_client=mqtt_client,
                frame=frame,
                snapshotter=snapshotter,
            )

    def _maybe_emit(
        self,
        *,
        event_type: str,
        objects: Iterable,
        classes: set[str],
        now_utc: datetime.datetime,
        after_hours: bool,
        cooldown_sec: int,
        last_emit_ref: str,
        present_ref: str,
        mqtt_client: MQTTClient,
        frame: Optional[Any],
        snapshotter,
    ) -> None:
        filtered = [
            obj for obj in objects
            if getattr(obj, "class_name", "").lower() in classes
            and getattr(obj, "confidence", 0.0) >= self.config.min_confidence
        ]
        count = len(filtered)
        was_present = getattr(self, present_ref)
        if count == 0:
            setattr(self, present_ref, False)
            return
        last_emit = getattr(self, last_emit_ref)
        should_emit = not was_present
        if last_emit is not None:
            elapsed = (now_utc - last_emit).total_seconds()
            if elapsed >= max(1, cooldown_sec):
                should_emit = True
        if not should_emit:
            setattr(self, present_ref, True)
            return
        event_id = str(uuid.uuid4())
        timestamp_iso = now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        bboxes = [getattr(obj, "bbox", None) for obj in filtered]
        bboxes = [bbox for bbox in bboxes if isinstance(bbox, list)]
        bboxes = bboxes[:5]
        max_conf = max((float(getattr(obj, "confidence", 0.0)) for obj in filtered), default=0.0)
        snapshot_url = None
        local_path = None
        if snapshotter is not None and frame is not None:
            try:
                label = "AfterHours Person" if event_type == "PERSON_DETECTED" else "AfterHours Vehicle"
                snapshot_url = snapshotter(frame, event_id, now_utc, bbox=bboxes[0] if bboxes else None, label=label)
            except Exception:
                snapshot_url = None
        if snapshot_url and not snapshot_url.startswith("http"):
            local_path = snapshot_url
        payload = PresencePayload(
            count=count,
            bbox=bboxes or None,
            confidence=max_conf if max_conf > 0 else None,
            is_after_hours=after_hours,
            evidence=PresenceEvidence(
                snapshot_url=snapshot_url,
                local_path=local_path,
                frame_ts=timestamp_iso,
            ),
        )
        event = PresenceEvent(
            event_id=event_id,
            occurred_at=timestamp_iso,
            timezone=self.config.timezone,
            godown_id=self.godown_id,
            camera_id=self.camera_id,
            event_type=event_type,
            payload=payload,
            correlation_id=str(uuid.uuid4()),
        )
        mqtt_client.publish_presence(event, http_fallback=self.config.http_fallback)
        setattr(self, last_emit_ref, now_utc)
        setattr(self, present_ref, True)
        self.logger.info(
            "After-hours presence event: type=%s camera=%s count=%d after_hours=%s",
            event_type,
            self.camera_id,
            count,
            after_hours,
        )
