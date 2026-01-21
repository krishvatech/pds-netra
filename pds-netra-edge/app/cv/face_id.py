"""
Face recognition utilities for PDS Netra.

This module provides functionality to load known face embeddings,
detect faces in frames, compute face embeddings for detected faces,
match embeddings against an authorised list of persons, and emit
structured events via MQTT when a face is identified or an unknown
face is observed. It is designed to be CPU-friendly and works
gracefully on Mac development machines.
"""

from __future__ import annotations

import logging
import json
import datetime
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

try:
    import numpy as np  # type: ignore
except ImportError:
    np = None  # type: ignore

try:
    import face_recognition  # type: ignore
except ImportError:
    face_recognition = None  # type: ignore

try:
    import cv2  # type: ignore
except ImportError:
    cv2 = None  # type: ignore

from zoneinfo import ZoneInfo

from ..config import FaceRecognitionConfig, FaceRecognitionCameraConfig
from ..cv.zones import is_bbox_in_zone
from ..models.event import EventModel, MetaModel
from ..events.mqtt_client import MQTTClient

import uuid


@dataclass
class KnownPerson:
    """Represents a known person with an embedding and metadata."""
    person_id: str
    name: str
    role: str
    embedding: List[float]


@dataclass
class MatchResult:
    """Result of matching a face embedding against known persons."""
    person_id: str
    person_name: str
    person_role: str
    confidence: float


def load_known_faces(file_path: str) -> List[KnownPerson]:
    """
    Load known person embeddings from a JSON file.

    The JSON file must contain a list of objects, each with keys:
    ``person_id``, ``name``, ``role``, and ``embedding`` (a list of floats).

    Parameters
    ----------
    file_path: str
        Path to the JSON file.

    Returns
    -------
    List[KnownPerson]
        Loaded list of KnownPerson objects. If file cannot be read or
        contains invalid data, an empty list is returned and a warning is
        logged.
    """
    logger = logging.getLogger("face_id")
    known: List[KnownPerson] = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            for item in data:
                try:
                    pid = item.get("person_id")
                    name = item.get("name")
                    role = item.get("role")
                    embedding = item.get("embedding")
                    if not (pid and name and role and isinstance(embedding, list)):
                        continue
                    embedding_float = [float(x) for x in embedding]
                    known.append(KnownPerson(person_id=pid, name=name, role=role, embedding=embedding_float))
                except Exception:
                    continue
    except Exception as exc:
        logger.warning("Failed to load known faces from %s: %s", file_path, exc)
    return known


def detect_faces(frame: any) -> List[List[int]]:
    """
    Detect face bounding boxes in a frame using face_recognition library.

    Parameters
    ----------
    frame: numpy.ndarray
        Image in BGR format.

    Returns
    -------
    List[List[int]]
        List of bounding boxes [x1, y1, x2, y2] for each detected face.
    """
    if face_recognition is None:
        return []
    rgb_frame = frame[:, :, ::-1]
    try:
        face_locations = face_recognition.face_locations(rgb_frame)
    except Exception:
        return []
    bboxes: List[List[int]] = []
    for top, right, bottom, left in face_locations:
        bboxes.append([left, top, right, bottom])
    return bboxes


def get_face_embedding(frame: any, bbox: List[int]) -> Optional[List[float]]:
    """
    Compute a face embedding for the region defined by bbox.

    Parameters
    ----------
    frame: numpy.ndarray
        The original image in BGR format.
    bbox: List[int]
        Bounding box [x1, y1, x2, y2] specifying the face region.

    Returns
    -------
    Optional[List[float]]
        The embedding vector (list of floats) if computation succeeds;
        otherwise, None.
    """
    if face_recognition is None:
        return None
    try:
        rgb_frame = frame[:, :, ::-1]
        top = bbox[1]
        left = bbox[0]
        bottom = bbox[3]
        right = bbox[2]
        locations = [(top, right, bottom, left)]
        encodings = face_recognition.face_encodings(rgb_frame, known_face_locations=locations)
        if encodings:
            return [float(x) for x in encodings[0]]
    except Exception:
        pass
    return None


def match_face(
    embedding: List[float],
    known_people: List[KnownPerson],
    min_confidence: float,
) -> Optional[MatchResult]:
    """
    Match a face embedding against known persons and return the best match
    if its confidence exceeds the threshold.

    Confidence is computed as (1 - Euclidean distance) between embeddings
    and clamped to [0, 1].

    Parameters
    ----------
    embedding: List[float]
        Embedding of the detected face.
    known_people: List[KnownPerson]
        List of known persons with embeddings to compare against.
    min_confidence: float
        Minimum confidence threshold to consider a match valid.

    Returns
    -------
    Optional[MatchResult]
        The best match if confidence >= min_confidence; otherwise None.
    """
    if face_recognition is None or not known_people:
        return None
    try:
        candidate = np.array(embedding)
    except Exception:
        return None
    known_embeddings = [np.array(kp.embedding) for kp in known_people]
    try:
        distances = face_recognition.face_distance(known_embeddings, candidate)
    except Exception:
        return None
    if len(distances) == 0:
        return None
    idx = int(distances.argmin())
    best_distance = float(distances[idx])
    confidence = max(0.0, 1.0 - best_distance)
    if confidence >= min_confidence:
        kp = known_people[idx]
        return MatchResult(
            person_id=kp.person_id,
            person_name=kp.name,
            person_role=kp.role,
            confidence=confidence,
        )
    return None


class FaceRecognitionProcessor:
    """
    Processor for face recognition logic. For a given camera, it detects
    faces, computes embeddings, matches them against known persons, and
    evaluates camera-specific policies to emit events via MQTT.
    """

    def __init__(
        self,
        camera_id: str,
        godown_id: str,
        camera_config: FaceRecognitionCameraConfig,
        global_config: FaceRecognitionConfig,
        zone_polygons: Dict[str, List[Tuple[int, int]]],
        timezone: str,
        known_people: List[KnownPerson],
    ) -> None:
        self.logger = logging.getLogger(f"FaceRecognitionProcessor-{camera_id}")
        self.camera_id = camera_id
        self.godown_id = godown_id
        self.camera_config = camera_config
        self.global_config = global_config
        self.zone_polygons = zone_polygons
        try:
            self.tz = ZoneInfo(timezone)
        except Exception:
            self.tz = ZoneInfo("UTC")
        self.known_people = known_people
        # Deduplication cache: maps (status, identifier) to last event time
        self.dedup_cache: Dict[Tuple[str, str], datetime.datetime] = {}

    def _determine_zone(self, bbox: List[int]) -> Optional[str]:
        """Return the zone ID whose polygon contains the bounding box center."""
        for zone_id, polygon in self.zone_polygons.items():
            if is_bbox_in_zone(bbox, polygon):
                return zone_id
        return None

    def _should_emit(self, key: Tuple[str, str], now: datetime.datetime) -> bool:
        """Determine if an event should be emitted based on dedup interval."""
        last = self.dedup_cache.get(key)
        if last is None:
            return True
        interval = self.global_config.dedup_interval_seconds
        if (now - last).total_seconds() >= interval:
            return True
        return False

    def _update_cache(self, key: Tuple[str, str], now: datetime.datetime) -> None:
        """Update dedup cache with the current timestamp for the given key."""
        self.dedup_cache[key] = now

    def process_frame(
        self,
        frame: any,
        now_utc: datetime.datetime,
        mqtt_client: MQTTClient,
    ) -> None:
        """
        Detect and recognize faces in the frame and publish events
        according to configured policies.

        Parameters
        ----------
        frame: numpy.ndarray
            The current frame in BGR format.
        now_utc: datetime.datetime
            Current UTC timestamp (aware or naive; will be treated as UTC).
        mqtt_client: MQTTClient
            Client used to publish events.
        """
        if frame is None:
            return
        if not self.global_config.enabled:
            return
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=datetime.timezone.utc)
        now_local = now_utc.astimezone(self.tz)
        timestamp_iso = now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        try:
            faces = detect_faces(frame)
        except Exception as exc:
            self.logger.error("Face detection failed: %s", exc)
            return
        for bbox in faces:
            zone_id = self._determine_zone(bbox)
            if zone_id is None or zone_id != self.camera_config.zone_id:
                continue
            embedding = get_face_embedding(frame, bbox)
            if embedding is None:
                continue
            match = match_face(embedding, self.known_people, self.global_config.min_match_confidence)
            match_status: str
            event_type: str
            severity: str
            person_id: Optional[str] = None
            person_name: Optional[str] = None
            person_role: Optional[str] = None
            confidence = 0.0
            if match is not None:
                match_status = "KNOWN"
                event_type = "FACE_IDENTIFIED"
                severity = "info"
                person_id = match.person_id
                person_name = match.person_name
                person_role = match.person_role
                confidence = match.confidence
            else:
                match_status = "UNKNOWN"
                event_type = "FACE_UNKNOWN_ACCESS"
                severity = "warning"
                confidence = 0.0
            if match_status == "UNKNOWN":
                if not self.camera_config.allow_unknown and self.global_config.unknown_event_enabled:
                    dedup_key = (match_status, self.camera_config.zone_id)
                    if not self._should_emit(dedup_key, now_utc):
                        continue
                    event = EventModel(
                        godown_id=self.godown_id,
                        camera_id=self.camera_id,
                        event_id=str(uuid.uuid4()),
                        event_type=event_type,
                        severity=severity,
                        timestamp_utc=timestamp_iso,
                        bbox=bbox,
                        track_id=0,
                        image_url=None,
                        clip_url=None,
                        meta=MetaModel(
                            zone_id=self.camera_config.zone_id,
                            rule_id=f"FACE_ID_POLICY_{self.camera_id}",
                            confidence=confidence,
                            person_id=None,
                            person_name=None,
                            person_role=None,
                            match_status=match_status,
                            extra={},
                        ),
                    )
                    mqtt_client.publish_event(event)
                    self._update_cache(dedup_key, now_utc)
                continue
            else:
                if self.camera_config.log_known_only:
                    dedup_key = (match_status, person_id or "")
                    if not self._should_emit(dedup_key, now_utc):
                        continue
                    event = EventModel(
                        godown_id=self.godown_id,
                        camera_id=self.camera_id,
                        event_id=str(uuid.uuid4()),
                        event_type=event_type,
                        severity=severity,
                        timestamp_utc=timestamp_iso,
                        bbox=bbox,
                        track_id=0,
                        image_url=None,
                        clip_url=None,
                        meta=MetaModel(
                            zone_id=self.camera_config.zone_id,
                            rule_id=f"FACE_ID_POLICY_{self.camera_id}",
                            confidence=confidence,
                            person_id=person_id,
                            person_name=person_name,
                            person_role=person_role,
                            match_status=match_status,
                            extra={},
                        ),
                    )
                    mqtt_client.publish_event(event)
                    self._update_cache(dedup_key, now_utc)
                else:
                    dedup_key = (match_status, person_id or "")
                    if not self._should_emit(dedup_key, now_utc):
                        continue
                    event = EventModel(
                        godown_id=self.godown_id,
                        camera_id=self.camera_id,
                        event_id=str(uuid.uuid4()),
                        event_type=event_type,
                        severity=severity,
                        timestamp_utc=timestamp_iso,
                        bbox=bbox,
                        track_id=0,
                        image_url=None,
                        clip_url=None,
                        meta=MetaModel(
                            zone_id=self.camera_config.zone_id,
                            rule_id=f"FACE_ID_POLICY_{self.camera_id}",
                            confidence=confidence,
                            person_id=person_id,
                            person_name=person_name,
                            person_role=person_role,
                            match_status=match_status,
                            extra={},
                        ),
                    )
                    mqtt_client.publish_event(event)
                    self._update_cache(dedup_key, now_utc)
