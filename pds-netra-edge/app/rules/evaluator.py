"""
Rule evaluation and loitering logic for PDS Netra.

This module implements logic to determine whether detected objects
violate configured rules and to manage loitering state. It can be
integrated into the pipeline callback to emit events through the
MQTT client when appropriate conditions are met.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Callable, Any

from zoneinfo import ZoneInfo
import math

from ..models.event import EventModel, MetaModel
from ..events.mqtt_client import MQTTClient
from ..cv.zones import is_bbox_in_zone
from ..cv.pipeline import DetectedObject
from .loader import (
    BaseRule,
    UnauthPersonAfterHoursRule,
    NoPersonDuringRule,
    LoiteringRule,
    AnimalForbiddenRule,
    BagMovementAfterHoursRule,
    BagMovementMonitorRule,
)

# Helper constants defining class names for animals and bags. These sets can
# be extended or customised according to YOLO26 output labels.
ANIMAL_CLASSES = {"dog", "cow", "bull", "cat", "rat"}
BAG_CLASSES = {"bag", "sack", "pallet", "trolley"}


@dataclass
class BagInfo:
    """
    Keeps track of a bag-like object's last known state.

    Attributes
    ----------
    last_zone_id: Optional[str]
        The zone in which the object was last seen; None if not in any zone.
    last_position: Tuple[float, float]
        The last observed centre (cx, cy) of the object.
    first_seen: datetime.datetime
        The timestamp when the object was first detected.
    last_seen: datetime.datetime
        The timestamp when the object was last detected.
    movement_reported: bool
        Flag indicating whether a movement event has been emitted for the current episode.
    """

    last_zone_id: Optional[str]
    last_position: Tuple[float, float]
    first_seen: datetime.datetime
    last_seen: datetime.datetime
    movement_reported: bool = False


def _parse_time_string(time_str: str) -> datetime.time:
    """Parse a HH:MM string into a datetime.time object."""
    try:
        return datetime.datetime.strptime(time_str, "%H:%M").time()
    except Exception:
        # Fallback to 00:00 if parsing fails
        return datetime.time(0, 0)


def _is_time_in_range(now_time: datetime.time, start_time: datetime.time, end_time: datetime.time) -> bool:
    """
    Determine if ``now_time`` lies within the half-open interval
    [start_time, end_time). Handles intervals that span midnight.
    """
    if start_time <= end_time:
        return start_time <= now_time < end_time
    else:
        # Interval spans midnight
        return now_time >= start_time or now_time < end_time


@dataclass
class TrackInfo:
    """Keeps track of an object's dwell time in a zone."""

    first_seen: datetime.datetime
    last_seen: datetime.datetime
    zone_id: str
    loitering_reported: bool = False


class RulesEvaluator:
    """
    Evaluates rules for detected persons and manages loitering state.

    One instance should be created per camera, along with its associated
    zone polygons and list of rules. The ``process_detections`` method
    can be called for each frame to update state and emit events via
    the provided MQTT client.
    """

    def __init__(
        self,
        camera_id: str,
        godown_id: str,
        rules: List[BaseRule],
        zone_polygons: Dict[str, List[Tuple[int, int]]],
        timezone: str,
        alert_on_person: bool = False,
        person_alert_cooldown_sec: int = 10,
        alert_classes: Optional[List[str]] = None,
        alert_severity: str = "warning",
        alert_min_conf: float = 0.0,
        zone_enforce: bool = True,
    ) -> None:
        self.logger = logging.getLogger(f"RulesEvaluator-{camera_id}")
        self.camera_id = camera_id
        self.godown_id = godown_id
        self.rules_by_zone: Dict[str, List[BaseRule]] = {}
        self.rule_zone_by_id: Dict[str, str] = {}
        for rule in rules:
            self.rules_by_zone.setdefault(rule.zone_id, []).append(rule)
            self.rule_zone_by_id[rule.id] = rule.zone_id
        self.zone_polygons = zone_polygons
        # Use zoneinfo for accurate timezone handling
        try:
            self.tz = ZoneInfo(timezone)
        except Exception:
            self.tz = ZoneInfo("UTC")
        self.track_history: Dict[Tuple[str, int], TrackInfo] = {}
        # Clean-up threshold (seconds) for stale track entries
        self.cleanup_threshold = 300  # 5 minutes

        # Track last alert time for animal intrusions keyed by (track_id, zone_id).
        self.animal_alerts: Dict[Tuple[int, str], datetime.datetime] = {}
        # Track bag state keyed by (camera_id, track_id). Each BagInfo holds
        # previous zone, position and whether movement has been reported.
        self.bag_state: Dict[Tuple[str, int], "BagInfo"] = {}
        # Cleanup threshold for stale bag and animal entries in seconds.
        self.bag_cleanup_threshold: int = 300
        # Track active persons by (rule_id, track_id) and last seen by (zone_id, track_id).
        self.person_active: set[Tuple[str, int]] = set()
        self.person_last_seen: Dict[Tuple[str, int], datetime.datetime] = {}
        self.person_exit_threshold_sec: int = 2
        # Instant alert controls (test mode)
        self.alert_on_person = alert_on_person
        self.person_alert_cooldown_sec = person_alert_cooldown_sec
        self.alert_classes = {c.strip().lower() for c in (alert_classes or []) if c.strip()}
        self.alert_severity = alert_severity
        self.alert_min_conf = alert_min_conf
        self.zone_enforce = zone_enforce
        self.person_alerts: Dict[Tuple[str, object, Optional[str]], datetime.datetime] = {}

    def _determine_zone(self, bbox: List[int]) -> Optional[str]:
        """
        Determine which zone a bounding box is in by testing its center
        against configured polygons. Returns the first matching zone_id or None.
        """
        for zone_id, polygon in self.zone_polygons.items():
            if is_bbox_in_zone(bbox, polygon):
                return zone_id
        return None

    def _evaluate_time_rules(
        self,
        rule: BaseRule,
        now_local: datetime.time,
    ) -> bool:
        """
        Evaluate time-based unauthorized person rules. Returns True if the
        rule conditions are satisfied (i.e., an unauthorized person is present).
        """
        if isinstance(rule, UnauthPersonAfterHoursRule):
            start_t = _parse_time_string(rule.start_time)
            end_t = _parse_time_string(rule.end_time)
            return _is_time_in_range(now_local, start_t, end_t)
        elif isinstance(rule, NoPersonDuringRule):
            start_t = _parse_time_string(rule.start)
            end_t = _parse_time_string(rule.end)
            return _is_time_in_range(now_local, start_t, end_t)
        return False

    def _cleanup_person_state(self, now_utc: datetime.datetime) -> None:
        """Expire person entries after they have left the scene."""
        stale_keys: List[Tuple[str, int]] = []
        for key, last_seen in self.person_last_seen.items():
            if (now_utc - last_seen).total_seconds() > self.person_exit_threshold_sec:
                stale_keys.append(key)
        if not stale_keys:
            return
        for zone_id, track_id in stale_keys:
            self.person_last_seen.pop((zone_id, track_id), None)
            to_remove = []
            for rule_id, active_track_id in self.person_active:
                if active_track_id != track_id:
                    continue
                if self.rule_zone_by_id.get(rule_id) == zone_id:
                    to_remove.append((rule_id, active_track_id))
            for key in to_remove:
                self.person_active.discard(key)

    def process_detections(
        self,
        objects: List[DetectedObject],
        now_utc: datetime.datetime,
        mqtt_client: MQTTClient,
        frame: Any = None,
        snapshotter: Optional[Callable[[Any, str, datetime.datetime], Optional[str]]] = None,
        instant_only: bool = False,
        meta_extra: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Evaluate all applicable rules for a batch of detected objects.

        This method handles unauthorized person detection, loitering,
        animal intrusion, and bag movement. It publishes events via the
        provided MQTT client when rule conditions are met. Stale
        histories for loitering, animal alerts and bag states are
        periodically cleaned up.

        Parameters
        ----------
        objects: List[DetectedObject]
            Detected objects from the current frame.
        now_utc: datetime.datetime
            Current time in UTC (naive or aware with UTC tz).
        mqtt_client: MQTTClient
            Client used to publish events.
        frame: Any
            Optional frame used for snapshot capture.
        snapshotter: Optional[Callable]
            Optional snapshot writer returning image URL/path.
        """
        # Ensure we have a timezone-aware UTC datetime
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=datetime.timezone.utc)
        now_local_dt = now_utc.astimezone(self.tz)
        now_local_time = now_local_dt.timetz()

        if instant_only:
            for obj in objects:
                cls = obj.class_name.lower()
                zone_id = self._determine_zone(obj.bbox)
                if cls in self.alert_classes:
                    self._process_instant_class_alert(
                        obj,
                        zone_id,
                        now_utc,
                        mqtt_client,
                        frame,
                        snapshotter,
                        meta_extra=meta_extra,
                    )
                elif cls == 'person' and self.alert_on_person:
                    self._process_person_instant(
                        obj,
                        zone_id,
                        now_utc,
                        mqtt_client,
                        frame,
                        snapshotter,
                        meta_extra=meta_extra,
                    )
            self._cleanup_person_alerts(now_utc)
            return
        for obj in objects:
            cls = obj.class_name.lower()
            zone_id = self._determine_zone(obj.bbox)
            if cls in self.alert_classes:
                self._process_instant_class_alert(
                    obj,
                    zone_id,
                    now_utc,
                    mqtt_client,
                    frame,
                    snapshotter,
                    meta_extra=meta_extra,
                )
            # Handle person-related rules (unauthorized presence and loitering)
            if cls == 'person':
                if self.alert_on_person:
                    self._process_person_instant(
                        obj,
                        zone_id,
                        now_utc,
                        mqtt_client,
                        frame,
                        snapshotter,
                        meta_extra=meta_extra,
                    )
                    self.logger.debug(
                        "Person detected: track_id=%s conf=%.3f zone=%s bbox=%s",
                        obj.track_id,
                        obj.confidence,
                        zone_id,
                        obj.bbox,
                    )
                if zone_id is None:
                    continue
                self.person_last_seen[(zone_id, obj.track_id)] = now_utc
                # Unauthorized person rules
                rules_for_zone = (
                    self.rules_by_zone.get(zone_id, [])
                    + self.rules_by_zone.get("all", [])
                    + self.rules_by_zone.get("*", [])
                )
                for rule in rules_for_zone:
                    if isinstance(rule, (UnauthPersonAfterHoursRule, NoPersonDuringRule)):
                        if self._evaluate_time_rules(rule, now_local_time):
                            entry_key = (rule.id, obj.track_id)
                            if entry_key not in self.person_active:
                                # Emit only once per entry; track until exit threshold expires.
                                severity = 'critical' if isinstance(rule, NoPersonDuringRule) else 'warning'
                                event = EventModel(
                                    godown_id=self.godown_id,
                                    camera_id=self.camera_id,
                                    event_id=str(uuid.uuid4()),
                                    event_type="UNAUTH_PERSON",
                                    severity=severity,
                                    timestamp_utc=now_utc.replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
                                    bbox=obj.bbox,
                                    track_id=obj.track_id,
                                    image_url=None,
                                    clip_url=None,
                                    meta=MetaModel(
                                        zone_id=zone_id,
                                        rule_id=rule.id,
                                        confidence=obj.confidence,
                                        extra={},
                                    ),
                                )
                                mqtt_client.publish_event(event)
                                self.person_active.add(entry_key)
                # Loitering rules
                for rule in rules_for_zone:
                    if isinstance(rule, LoiteringRule):
                        self._process_loitering(rule, obj, zone_id, now_utc, mqtt_client, frame, snapshotter)
                continue  # person handled

            # Handle animal intrusion
            if cls in ANIMAL_CLASSES:
                if zone_id is None:
                    continue
                rules_for_zone = (
                    self.rules_by_zone.get(zone_id, [])
                    + self.rules_by_zone.get("all", [])
                    + self.rules_by_zone.get("*", [])
                )
                for rule in rules_for_zone:
                    if isinstance(rule, AnimalForbiddenRule):
                        self._process_animal(rule, obj, zone_id, now_utc, mqtt_client, frame, snapshotter)
                continue

            # Handle bag movement
            if cls in BAG_CLASSES:
                # zone_id may be None when bag is outside defined zones
                self._process_bag(obj, zone_id, now_utc, now_local_time, mqtt_client, frame, snapshotter)
                continue

            # Other classes are ignored
            continue

        # Clean up stale state
        self._cleanup_person_state(now_utc)
        self._cleanup_history(now_utc)
        self._cleanup_animal_alerts(now_utc)
        self._cleanup_bag_state(now_utc)
        self._cleanup_person_alerts(now_utc)

    def _process_loitering(
        self,
        rule: LoiteringRule,
        obj: DetectedObject,
        zone_id: str,
        now_utc: datetime.datetime,
        mqtt_client: MQTTClient,
        frame: Any = None,
        snapshotter: Optional[Callable[[Any, str, datetime.datetime], Optional[str]]] = None,
    ) -> None:
        """
        Update tracking history for loitering and publish an event if the
        dwell time exceeds the threshold.
        """
        key = (self.camera_id, obj.track_id)
        entry = self.track_history.get(key)
        if entry is None or entry.zone_id != zone_id:
            # New track or moved to a different zone: reset
            self.track_history[key] = TrackInfo(
                first_seen=now_utc,
                last_seen=now_utc,
                zone_id=zone_id,
                loitering_reported=False,
            )
            return
        # Update last seen
        entry.last_seen = now_utc
        if not entry.loitering_reported:
            dwell_seconds = (entry.last_seen - entry.first_seen).total_seconds()
            if dwell_seconds >= rule.threshold_seconds:
                # Publish loitering event
                event_id = str(uuid.uuid4())
                event = EventModel(
                    godown_id=self.godown_id,
                    camera_id=self.camera_id,
                    event_id=event_id,
                    event_type="LOITERING",
                    severity="warning",
                    timestamp_utc=now_utc.replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
                    bbox=obj.bbox,
                    track_id=obj.track_id,
                    image_url=self._snapshot(frame, snapshotter, event_id, now_utc, bbox=obj.bbox, label=obj.class_name),
                    clip_url=None,
                    meta=MetaModel(
                        zone_id=zone_id,
                        rule_id=rule.id,
                        confidence=obj.confidence,
                        extra={},
                    ),
                )
                mqtt_client.publish_event(event)
                entry.loitering_reported = True

    def _cleanup_history(self, now_utc: datetime.datetime) -> None:
        """
        Remove entries from ``track_history`` that have not been seen for
        longer than ``cleanup_threshold`` seconds.
        """
        to_delete: List[Tuple[str, int]] = []
        for key, entry in self.track_history.items():
            if (now_utc - entry.last_seen).total_seconds() > self.cleanup_threshold:
                to_delete.append(key)
        for key in to_delete:
            self.track_history.pop(key, None)

    def _cleanup_animal_alerts(self, now_utc: datetime.datetime) -> None:
        """
        Remove animal alert entries that have not been refreshed for more than
        ``bag_cleanup_threshold`` seconds. This allows animals returning after
        a significant time to trigger a new alert.
        """
        to_remove: List[Tuple[int, str]] = []
        for key, last_alert_time in self.animal_alerts.items():
            if (now_utc - last_alert_time).total_seconds() > self.bag_cleanup_threshold:
                to_remove.append(key)
        for key in to_remove:
            self.animal_alerts.pop(key, None)

    def _cleanup_bag_state(self, now_utc: datetime.datetime) -> None:
        """
        Remove bag state entries that have not been seen for more than
        ``bag_cleanup_threshold`` seconds to free memory and allow new
        movement episodes for the same track.
        """
        to_remove: List[Tuple[str, int]] = []
        for key, info in self.bag_state.items():
            if (now_utc - info.last_seen).total_seconds() > self.bag_cleanup_threshold:
                to_remove.append(key)
        for key in to_remove:
            self.bag_state.pop(key, None)

    def _process_animal(
        self,
        rule: AnimalForbiddenRule,
        obj: DetectedObject,
        zone_id: str,
        now_utc: datetime.datetime,
        mqtt_client: MQTTClient,
        frame: Any = None,
        snapshotter: Optional[Callable[[Any, str, datetime.datetime], Optional[str]]] = None,
    ) -> None:
        """
        Handle animal intrusion events. An event is published the first time a
        track enters a forbidden zone, and subsequent occurrences are
        suppressed until the alert entry is cleaned up.

        Parameters
        ----------
        rule: AnimalForbiddenRule
            The rule being evaluated.
        obj: DetectedObject
            The detected object considered an animal.
        zone_id: str
            The ID of the zone where the object is located.
        now_utc: datetime.datetime
            Current UTC time.
        mqtt_client: MQTTClient
            Client used to publish events.
        """
        key = (obj.track_id, zone_id)
        last_alert_time = self.animal_alerts.get(key)
        if last_alert_time is not None:
            # Suppress duplicate alerts for the same track in the same zone
            return
        # Publish animal intrusion event
        event_id = str(uuid.uuid4())
        event = EventModel(
            godown_id=self.godown_id,
            camera_id=self.camera_id,
            event_id=event_id,
            event_type="ANIMAL_INTRUSION",
            severity="warning",
            timestamp_utc=now_utc.replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
            bbox=obj.bbox,
            track_id=obj.track_id,
            image_url=self._snapshot(frame, snapshotter, event_id, now_utc, bbox=obj.bbox, label=obj.class_name),
            clip_url=None,
            meta=MetaModel(
                zone_id=zone_id,
                rule_id=rule.id,
                confidence=obj.confidence,
                movement_type=None,
                extra={},
            ),
        )
        mqtt_client.publish_event(event)
        # Record the alert time for deduplication
        self.animal_alerts[key] = now_utc

    def _process_person_instant(
        self,
        obj: DetectedObject,
        zone_id: Optional[str],
        now_utc: datetime.datetime,
        mqtt_client: MQTTClient,
        frame: Any = None,
        snapshotter: Optional[Callable[[Any, str, datetime.datetime], Optional[str]]] = None,
        meta_extra: Optional[Dict[str, str]] = None,
    ) -> None:
        if obj.confidence < self.alert_min_conf:
            return
        if self.zone_enforce and not zone_id:
            return
        key = (self.camera_id, obj.track_id, zone_id)
        last_alert = self.person_alerts.get(key)
        if last_alert and (now_utc - last_alert).total_seconds() < self.person_alert_cooldown_sec:
            return
        event_id = str(uuid.uuid4())
        event = EventModel(
            godown_id=self.godown_id,
            camera_id=self.camera_id,
            event_id=event_id,
            event_type="UNAUTH_PERSON",
            severity=self.alert_severity,
            timestamp_utc=now_utc.replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
            bbox=obj.bbox,
            track_id=obj.track_id,
            image_url=self._snapshot(frame, snapshotter, event_id, now_utc, bbox=obj.bbox, label=obj.class_name),
            clip_url=None,
            meta=MetaModel(
                zone_id=zone_id or "",
                rule_id="TEST_PERSON_DETECT",
                confidence=obj.confidence,
                extra=dict(meta_extra or {}),
            ),
        )
        mqtt_client.publish_event(event)
        self.person_alerts[key] = now_utc

    def _process_instant_class_alert(
        self,
        obj: DetectedObject,
        zone_id: Optional[str],
        now_utc: datetime.datetime,
        mqtt_client: MQTTClient,
        frame: Any = None,
        snapshotter: Optional[Callable[[Any, str, datetime.datetime], Optional[str]]] = None,
        meta_extra: Optional[Dict[str, str]] = None,
    ) -> None:
        if obj.confidence < self.alert_min_conf:
            return
        if self.zone_enforce and not zone_id:
            return
        class_key = obj.class_name.lower()
        key = (self.camera_id, class_key, zone_id)
        last_alert = self.person_alerts.get(key)
        if last_alert and (now_utc - last_alert).total_seconds() < self.person_alert_cooldown_sec:
            return
        event_id = str(uuid.uuid4())
        event = EventModel(
            godown_id=self.godown_id,
            camera_id=self.camera_id,
            event_id=event_id,
            event_type="UNAUTH_PERSON",
            severity=self.alert_severity,
            timestamp_utc=now_utc.replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
            bbox=obj.bbox,
            track_id=obj.track_id,
            image_url=self._snapshot(frame, snapshotter, event_id, now_utc, bbox=obj.bbox, label=obj.class_name),
            clip_url=None,
            meta=MetaModel(
                zone_id=zone_id or "",
                rule_id="TEST_CLASS_DETECT",
                confidence=obj.confidence,
                movement_type=obj.class_name,
                extra=dict(meta_extra or {}),
            ),
        )
        mqtt_client.publish_event(event)
        self.person_alerts[key] = now_utc

    def _is_within_window(
        self, start_str: Optional[str], end_str: Optional[str], now_local_time: datetime.time
    ) -> bool:
        """
        Generic helper to determine if the current local time lies within a
        specified start and end (HH:MM) interval. Handles windows that
        cross midnight.
        """
        if not start_str or not end_str:
            # No explicit window defined; always active
            return True
        start_t = _parse_time_string(start_str)
        end_t = _parse_time_string(end_str)
        return _is_time_in_range(now_local_time, start_t, end_t)

    def _process_bag(
        self,
        obj: DetectedObject,
        zone_id: Optional[str],
        now_utc: datetime.datetime,
        now_local_time: datetime.time,
        mqtt_client: MQTTClient,
        frame: Any = None,
        snapshotter: Optional[Callable[[Any, str, datetime.datetime], Optional[str]]] = None,
    ) -> None:
        """
        Handle bag movement logic for monitored zones.

        Depending on configured rules, movement events are triggered when
        bags move significantly or enter specific zones during after-hours.

        Parameters
        ----------
        obj: DetectedObject
            The detected bag-like object.
        zone_id: Optional[str]
            The zone in which the object currently resides, or None if outside.
        now_utc: datetime.datetime
            The current UTC time.
        now_local_time: datetime.time
            The current local time in the configured timezone.
        mqtt_client: MQTTClient
            MQTT client used to publish events.
        """
        key = (self.camera_id, obj.track_id)
        cx = (obj.bbox[0] + obj.bbox[2]) / 2.0
        cy = (obj.bbox[1] + obj.bbox[3]) / 2.0
        current_pos = (cx, cy)
        info = self.bag_state.get(key)
        if info is None:
            # Initialise new bag entry
            self.bag_state[key] = BagInfo(
                last_zone_id=zone_id,
                last_position=current_pos,
                first_seen=now_utc,
                last_seen=now_utc,
                movement_reported=False,
            )
            return
        # Update last seen time
        info.last_seen = now_utc
        # Check if zone has changed
        zone_changed = (zone_id != info.last_zone_id)
        # Compute displacement since last frame
        dx = current_pos[0] - info.last_position[0]
        dy = current_pos[1] - info.last_position[1]
        distance_moved = math.hypot(dx, dy)
        # Determine applicable rules for current zone (if any) and previous zone
        # Bag movement events are emitted only when the object is within a defined zone.
        rules_current_zone = self.rules_by_zone.get(zone_id, []) if zone_id is not None else []
        # Determine whether movement has occurred based on zone or distance
        movement_occurred = zone_changed or (distance_moved > 0)
        # Only emit a new event if movement occurred and we haven't reported before
        if movement_occurred and not info.movement_reported:
            # Evaluate each rule in the current zone, prioritising after-hours rules
            event_emitted = False
            for rule in rules_current_zone:
                if isinstance(rule, BagMovementAfterHoursRule):
                    # Check time window
                    if self._is_within_window(rule.start_time, rule.end_time, now_local_time):
                        # Movement must exceed a basic threshold to avoid noise
                        # Use a default of 50 pixels
                        if zone_changed or distance_moved >= 50:
                            event_id = str(uuid.uuid4())
                            event = EventModel(
                                godown_id=self.godown_id,
                                camera_id=self.camera_id,
                                event_id=event_id,
                                event_type="BAG_MOVEMENT",
                                severity="warning",
                                timestamp_utc=now_utc.replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
                                bbox=obj.bbox,
                                track_id=obj.track_id,
                                image_url=self._snapshot(frame, snapshotter, event_id, now_utc, bbox=obj.bbox, label=obj.class_name),
                                clip_url=None,
                                meta=MetaModel(
                                    zone_id=zone_id or (info.last_zone_id or ""),
                                    rule_id=rule.id,
                                    confidence=obj.confidence,
                                    movement_type="AFTER_HOURS",
                                    extra={},
                                ),
                            )
                            mqtt_client.publish_event(event)
                            info.movement_reported = True
                            event_emitted = True
                            break
                elif isinstance(rule, BagMovementMonitorRule):
                    # Generic movement monitoring: check threshold distance
                    threshold = getattr(rule, 'threshold_distance', 50)
                    if zone_changed or distance_moved >= threshold:
                        event_id = str(uuid.uuid4())
                        event = EventModel(
                            godown_id=self.godown_id,
                            camera_id=self.camera_id,
                            event_id=event_id,
                            event_type="BAG_MOVEMENT",
                            severity="warning",
                            timestamp_utc=now_utc.replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
                            bbox=obj.bbox,
                            track_id=obj.track_id,
                            image_url=self._snapshot(frame, snapshotter, event_id, now_utc, bbox=obj.bbox, label=obj.class_name),
                            clip_url=None,
                            meta=MetaModel(
                                zone_id=zone_id or (info.last_zone_id or ""),
                                rule_id=rule.id,
                                confidence=obj.confidence,
                                movement_type="GENERIC",
                                extra={},
                            ),
                        )
                        mqtt_client.publish_event(event)
                        info.movement_reported = True
                        event_emitted = True
                        break
            # If no rule matched or no rule exists, no event is emitted
        # Update the bag state for next iteration
        info.last_position = current_pos
        info.last_zone_id = zone_id

    def _cleanup_person_alerts(self, now_utc: datetime.datetime) -> None:
        to_remove: List[Tuple[str, int, Optional[str]]] = []
        for key, ts in self.person_alerts.items():
            if (now_utc - ts).total_seconds() > self.bag_cleanup_threshold:
                to_remove.append(key)
        for key in to_remove:
            self.person_alerts.pop(key, None)

    @staticmethod
    def _snapshot(
        frame: Any,
        snapshotter: Optional[Callable[..., Optional[str]]],
        event_id: str,
        now_utc: datetime.datetime,
        bbox: Optional[List[int]] = None,
        label: Optional[str] = None,
    ) -> Optional[str]:
        if frame is None or snapshotter is None:
            return None
        try:
            return snapshotter(frame, event_id, now_utc, bbox=bbox, label=label)
        except Exception:
            return None
