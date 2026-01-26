"""
Bag movement tracking and event generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import uuid

from zoneinfo import ZoneInfo

from .zones import is_bbox_in_zone
from .pipeline import DetectedObject
from ..events.mqtt_client import MQTTClient
from ..models.event import EventModel, MetaModel
from ..rules.loader import (
    BagMonitorRule,
    BagOddHoursRule,
    BagUnplannedRule,
    BagTallyMismatchRule,
)


@dataclass
class DispatchPlan:
    plan_id: str
    camera_id: str
    zone_id: str
    start_utc: datetime.datetime
    end_utc: datetime.datetime
    expected_bag_count: int


@dataclass
class PlanState:
    observed_count: int = 0
    seen_track_ids: Set[int] = field(default_factory=set)


@dataclass
class BagTrackState:
    last_center: Tuple[float, float]
    last_seen: datetime.datetime
    last_in_zone: bool
    last_zone_id: Optional[str]


class DispatchPlanStore:
    def __init__(self, path: str, reload_interval_sec: int = 10) -> None:
        self.path = Path(path).expanduser()
        self.reload_interval_sec = max(1, int(reload_interval_sec))
        self._last_mtime: float = 0.0
        self._last_check: float = 0.0
        self.plans: List[DispatchPlan] = []

    def _parse_ts(self, ts: str) -> Optional[datetime.datetime]:
        if not ts:
            return None
        try:
            if ts.endswith("Z"):
                ts = ts.replace("Z", "+00:00")
            return datetime.datetime.fromisoformat(ts).astimezone(datetime.timezone.utc)
        except Exception:
            return None

    def _load(self) -> None:
        if not self.path.exists():
            self.plans = []
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            self.plans = []
            return
        plans: List[DispatchPlan] = []
        for plan in payload.get("plans", []) if isinstance(payload, dict) else []:
            try:
                plan_id = str(plan.get("plan_id") or "")
                camera_id = str(plan.get("camera_id") or "")
                zone_id = str(plan.get("zone_id") or "")
                start = self._parse_ts(plan.get("start_utc") or "")
                end = self._parse_ts(plan.get("end_utc") or "")
                expected = int(plan.get("expected_bag_count") or 0)
                if not (plan_id and camera_id and zone_id and start and end):
                    continue
                plans.append(
                    DispatchPlan(
                        plan_id=plan_id,
                        camera_id=camera_id,
                        zone_id=zone_id,
                        start_utc=start,
                        end_utc=end,
                        expected_bag_count=max(0, expected),
                    )
                )
            except Exception:
                continue
        self.plans = plans

    def refresh_if_needed(self, now_ts: float) -> None:
        if now_ts - self._last_check < self.reload_interval_sec:
            return
        self._last_check = now_ts
        try:
            mtime = self.path.stat().st_mtime
        except Exception:
            mtime = 0.0
        if mtime == self._last_mtime:
            return
        self._last_mtime = mtime
        self._load()

    def active_plans(
        self,
        camera_id: str,
        zone_id: str,
        now_utc: datetime.datetime,
    ) -> List[DispatchPlan]:
        return [
            plan
            for plan in self.plans
            if plan.camera_id == camera_id
            and plan.zone_id == zone_id
            and plan.start_utc <= now_utc <= plan.end_utc
        ]


class BagMovementProcessor:
    def __init__(
        self,
        camera_id: str,
        godown_id: str,
        zone_polygons: Dict[str, List[Tuple[int, int]]],
        rules: List[object],
        timezone: str,
        dispatch_plan_path: str,
        dispatch_plan_reload_sec: int,
        bag_class_keywords: List[str],
        movement_px_threshold: int = 50,
        movement_time_window_sec: int = 2,
    ) -> None:
        self.logger = logging.getLogger(f"BagMovement-{camera_id}")
        self.camera_id = camera_id
        self.godown_id = godown_id
        self.zone_polygons = zone_polygons
        self.tz = ZoneInfo(timezone or "UTC")
        self.plan_store = DispatchPlanStore(dispatch_plan_path, dispatch_plan_reload_sec)
        self.bag_class_keywords = [kw.strip().lower() for kw in bag_class_keywords if kw.strip()]
        self.movement_px_threshold = max(1, int(movement_px_threshold))
        self.movement_time_window_sec = max(1, int(movement_time_window_sec))
        self.track_states: Dict[int, BagTrackState] = {}
        self.plan_states: Dict[str, PlanState] = {}
        self.last_emit: Dict[Tuple[str, str], datetime.datetime] = {}
        self.rules_monitor = [r for r in rules if isinstance(r, BagMonitorRule)]
        self.rules_odd = [r for r in rules if isinstance(r, BagOddHoursRule)]
        self.rules_unplanned = [r for r in rules if isinstance(r, BagUnplannedRule)]
        self.rules_tally = [r for r in rules if isinstance(r, BagTallyMismatchRule)]

    def update_rules(self, rules: List[object]) -> None:
        """Replace rule lists in-place for dynamic updates."""
        self.rules_monitor = [r for r in rules if isinstance(r, BagMonitorRule)]
        self.rules_odd = [r for r in rules if isinstance(r, BagOddHoursRule)]
        self.rules_unplanned = [r for r in rules if isinstance(r, BagUnplannedRule)]
        self.rules_tally = [r for r in rules if isinstance(r, BagTallyMismatchRule)]

    def _is_bag_class(self, class_name: str) -> bool:
        name = class_name.lower()
        return any(keyword in name for keyword in self.bag_class_keywords)

    def _determine_zone(self, bbox: List[int]) -> Optional[str]:
        for zone_id, polygon in self.zone_polygons.items():
            if is_bbox_in_zone(bbox, polygon):
                return zone_id
        return None

    def _time_in_range(self, now_local: datetime.time, start_str: str, end_str: str) -> bool:
        try:
            start_t = datetime.datetime.strptime(start_str, "%H:%M").time()
            end_t = datetime.datetime.strptime(end_str, "%H:%M").time()
        except Exception:
            return False
        if start_t <= end_t:
            return start_t <= now_local < end_t
        return now_local >= start_t or now_local < end_t

    def _zone_match(self, rule_zone: str, zone_id: str) -> bool:
        rule_zone = (rule_zone or "").lower()
        return rule_zone in {"all", "*"} or rule_zone == zone_id.lower()

    def _cooldown_ok(self, zone_id: str, movement_type: str, cooldown_seconds: int, now_utc: datetime.datetime) -> bool:
        key = (zone_id, movement_type)
        last = self.last_emit.get(key)
        if last and (now_utc - last).total_seconds() < cooldown_seconds:
            return False
        self.last_emit[key] = now_utc
        return True

    def _emit_event(
        self,
        obj: DetectedObject,
        zone_id: str,
        movement_type: str,
        rule_id: str,
        now_utc: datetime.datetime,
        mqtt_client: MQTTClient,
        frame=None,
        snapshotter=None,
        extra: Optional[Dict[str, str]] = None,
    ) -> None:
        event_id = str(uuid.uuid4())
        image_url = None
        if snapshotter is not None and frame is not None:
            try:
                image_url = snapshotter(frame, event_id, now_utc, bbox=obj.bbox, label=obj.class_name)
            except Exception:
                image_url = None
        severity = "info" if movement_type == "NORMAL" else "warning"
        if movement_type == "TALLY_MISMATCH":
            severity = "critical"
        meta_extra = {k: str(v) for k, v in (extra or {}).items() if v is not None}
        plan_id = meta_extra.get("plan_id") if meta_extra else None
        event = EventModel(
            godown_id=self.godown_id,
            camera_id=self.camera_id,
            event_id=event_id,
            event_type="BAG_MOVEMENT",
            severity=severity,
            timestamp_utc=now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            bbox=obj.bbox,
            track_id=obj.track_id,
            image_url=image_url,
            clip_url=None,
            meta=MetaModel(
                zone_id=zone_id,
                rule_id=rule_id,
                confidence=obj.confidence,
                movement_type=movement_type,
                extra=meta_extra,
            ),
        )
        mqtt_client.publish_event(event)
        self.logger.info(
            "Bag movement emitted: camera=%s zone=%s plan=%s type=%s rule=%s track=%s",
            self.camera_id,
            zone_id,
            plan_id or "-",
            movement_type,
            rule_id,
            obj.track_id,
        )

    def _update_plan_counts(self, plan: DispatchPlan, track_id: int) -> int:
        state = self.plan_states.setdefault(plan.plan_id, PlanState())
        if track_id not in state.seen_track_ids:
            state.seen_track_ids.add(track_id)
            state.observed_count += 1
        return state.observed_count

    def process(
        self,
        objects: List[DetectedObject],
        now_utc: datetime.datetime,
        mqtt_client: MQTTClient,
        frame=None,
        snapshotter=None,
    ) -> None:
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=datetime.timezone.utc)
        now_local = now_utc.astimezone(self.tz).replace(tzinfo=None).time()
        self.plan_store.refresh_if_needed(time.time())
        active_plan_ids = {plan.plan_id for plan in self.plan_store.plans}
        for plan_id in list(self.plan_states.keys()):
            if plan_id not in active_plan_ids:
                self.plan_states.pop(plan_id, None)

        for obj in objects:
            if obj.track_id < 0:
                continue
            if not self._is_bag_class(obj.class_name):
                continue
            zone_id = self._determine_zone(obj.bbox)
            in_zone = zone_id is not None
            track_state = self.track_states.get(obj.track_id)
            movement_event = False
            event_zone_id: Optional[str] = None
            if track_state is None:
                movement_event = bool(in_zone)
                self.track_states[obj.track_id] = BagTrackState(
                    last_center=self._center(obj.bbox),
                    last_seen=now_utc,
                    last_in_zone=in_zone,
                    last_zone_id=zone_id,
                )
                if in_zone:
                    event_zone_id = zone_id
            else:
                dist = self._distance(track_state.last_center, self._center(obj.bbox))
                dt = (now_utc - track_state.last_seen).total_seconds()
                moved = dist >= self.movement_px_threshold and dt <= self.movement_time_window_sec
                zone_changed = track_state.last_in_zone != in_zone or (
                    in_zone and track_state.last_zone_id != zone_id
                )
                movement_event = moved or zone_changed
                if in_zone:
                    event_zone_id = zone_id
                elif zone_changed and track_state.last_zone_id:
                    event_zone_id = track_state.last_zone_id
                track_state.last_center = self._center(obj.bbox)
                track_state.last_seen = now_utc
                track_state.last_in_zone = in_zone
                track_state.last_zone_id = zone_id

            if not movement_event or not event_zone_id:
                continue

            active_plans = self.plan_store.active_plans(self.camera_id, event_zone_id, now_utc)
            active_plan = active_plans[0] if active_plans else None

            # Update tally counts for active plan
            observed_count = None
            if in_zone and active_plan is not None:
                observed_count = self._update_plan_counts(active_plan, obj.track_id)

            # Tally mismatch
            for rule in self.rules_tally:
                if not self._zone_match(rule.zone_id, event_zone_id):
                    continue
                if active_plan is None or observed_count is None:
                    continue
                allowed = 1 + (rule.allowed_overage_percent / 100.0)
                threshold = int(active_plan.expected_bag_count * allowed)
                if observed_count > threshold:
                    if self._cooldown_ok(event_zone_id, "TALLY_MISMATCH", rule.cooldown_seconds, now_utc):
                        self._emit_event(
                            obj,
                            event_zone_id,
                            "TALLY_MISMATCH",
                            rule.id,
                            now_utc,
                            mqtt_client,
                            frame,
                            snapshotter,
                            extra={
                                "plan_id": active_plan.plan_id,
                                "expected_bag_count": active_plan.expected_bag_count,
                                "observed_bag_count": observed_count,
                                "allowed_overage_percent": rule.allowed_overage_percent,
                            },
                        )
                    return

            # Odd hours
            for rule in self.rules_odd:
                if not self._zone_match(rule.zone_id, event_zone_id):
                    continue
                if self._time_in_range(now_local, rule.start_local, rule.end_local):
                    if self._cooldown_ok(event_zone_id, "ODD_HOURS", rule.cooldown_seconds, now_utc):
                        self._emit_event(
                            obj,
                            event_zone_id,
                            "ODD_HOURS",
                            rule.id,
                            now_utc,
                            mqtt_client,
                            frame,
                            snapshotter,
                            extra={
                                "plan_id": active_plan.plan_id if active_plan else None,
                            },
                        )
                    return

            # Unplanned movement
            for rule in self.rules_unplanned:
                if not self._zone_match(rule.zone_id, event_zone_id):
                    continue
                if rule.require_active_dispatch_plan and active_plan is None:
                    if self._cooldown_ok(event_zone_id, "UNPLANNED", rule.cooldown_seconds, now_utc):
                        self._emit_event(
                            obj,
                            event_zone_id,
                            "UNPLANNED",
                            rule.id,
                            now_utc,
                            mqtt_client,
                            frame,
                            snapshotter,
                            extra={
                                "plan_id": active_plan.plan_id if active_plan else None,
                            },
                        )
                    return

            # Normal monitoring
            for rule in self.rules_monitor:
                if not self._zone_match(rule.zone_id, event_zone_id):
                    continue
                if self._cooldown_ok(event_zone_id, "NORMAL", rule.cooldown_seconds, now_utc):
                    self._emit_event(
                        obj,
                        event_zone_id,
                        "NORMAL",
                        rule.id,
                        now_utc,
                        mqtt_client,
                        frame,
                        snapshotter,
                        extra={
                            "plan_id": active_plan.plan_id if active_plan else None,
                            "observed_bag_count": observed_count,
                        },
                    )
                return

    @staticmethod
    def _center(bbox: List[int]) -> Tuple[float, float]:
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @staticmethod
    def _distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        dx = p1[0] - p2[0]
        dy = p1[1] - p2[1]
        return (dx * dx + dy * dy) ** 0.5
