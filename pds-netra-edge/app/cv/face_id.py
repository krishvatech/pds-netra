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
import os
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

try:
    import numpy as np  # type: ignore
except ImportError:
    np = None  # type: ignore

try:
    from insightface.app import FaceAnalysis  # type: ignore
except ImportError:
    FaceAnalysis = None  # type: ignore

try:
    import faiss  # type: ignore
    _FAISS_OK = True
except Exception:
    faiss = None  # type: ignore
    _FAISS_OK = False

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


@dataclass
class FaceOverlay:
    """Overlay metadata for drawing face recognition results."""
    bbox: List[int]
    status: str
    person_id: Optional[str]
    person_name: Optional[str]
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


_face_app: Optional["FaceAnalysis"] = None


def _ensure_model() -> "FaceAnalysis":
    if FaceAnalysis is None:
        raise RuntimeError("insightface is not installed; please install insightface to use face recognition")

    global _face_app
    if _face_app is not None:
        return _face_app

    logger = logging.getLogger("face_id")
    model_name = os.getenv("PDS_FACE_MODEL", "antelopev2")
    root = os.getenv("INSIGHTFACE_HOME", os.path.expanduser("~/.insightface"))

    def _init(name: str) -> "FaceAnalysis":
        # allowed_modules is optional but keeps it lean/faster
        app = FaceAnalysis(name=name, root=root, allowed_modules=["detection", "recognition"])
        app.prepare(ctx_id=-1, det_size=(640, 640))
        return app

    try:
        _face_app = _init(model_name)
    except AssertionError:
        logger.error(
            "InsightFace model '%s' loaded without 'detection'. "
            "This usually means the model files are missing or stored in a nested folder. "
            "Check %s/models/%s for *.onnx files (no extra subfolder).",
            model_name, root, model_name
        )
        if model_name != "buffalo_l":
            logger.warning("Falling back to buffalo_l.")
            _face_app = _init("buffalo_l")
        else:
            raise

    return _face_app


def _l2_normalize(arr: "np.ndarray") -> "np.ndarray":
    if np is None:
        return arr
    norm = float(np.linalg.norm(arr))
    if norm > 0:
        return arr / norm
    return arr


class _FaceIndex:
    def __init__(self, dim: int = 512) -> None:
        self.dim = dim
        self.ids: List[int] = []
        if _FAISS_OK:
            self.index = faiss.IndexFlatIP(self.dim)  # type: ignore[attr-defined]
        else:
            self.index = None
            self._mat: Optional["np.ndarray"] = None

    def build(self, embeddings: "np.ndarray", ids: List[int]) -> None:
        if np is None or embeddings.size == 0:
            self.ids = []
            self._mat = None
            if _FAISS_OK:
                self.index = faiss.IndexFlatIP(self.dim)  # type: ignore[attr-defined]
            return
        embeddings = embeddings.astype("float32")
        self.dim = int(embeddings.shape[1])
        self.ids = list(ids)
        if _FAISS_OK:
            self.index = faiss.IndexFlatIP(self.dim)  # type: ignore[attr-defined]
            self.index.add(embeddings)
        else:
            self._mat = embeddings

    def ready(self) -> bool:
        return bool(self.ids)

    def query(self, embedding: "np.ndarray", k: int = 1) -> Optional[Tuple[int, float]]:
        if np is None or not self.ready():
            return None
        vec = embedding.astype("float32").reshape(1, -1)
        if _FAISS_OK and self.index is not None:
            scores, idx = self.index.search(vec, k)
            if idx.size == 0:
                return None
            match_idx = int(idx[0][0])
            if match_idx < 0 or match_idx >= len(self.ids):
                return None
            return self.ids[match_idx], float(scores[0][0])
        if self._mat is None:
            return None
        scores = vec @ self._mat.T
        match_idx = int(scores.argmax())
        return self.ids[match_idx], float(scores[0][match_idx])


def detect_faces(frame: any) -> List[Tuple[List[int], List[float]]]:
    """
    Detect face bounding boxes and embeddings using InsightFace.

    Parameters
    ----------
    frame: numpy.ndarray
        Image in BGR format.

    Returns
    -------
    List[Tuple[List[int], List[float]]]
        List of (bbox, embedding) pairs, bbox is [x1, y1, x2, y2].
    """
    if np is None:
        return []
    app = _ensure_model()
    try:
        faces = app.get(frame)
    except Exception as e:
        return []
    results: List[Tuple[List[int], List[float]]] = []
    for face in faces:
        emb = face.embedding
        emb = _l2_normalize(emb)
        bbox = face.bbox.tolist()
        results.append(([int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])], [float(x) for x in emb]))
    return results


def match_face(
    embedding: List[float],
    index: _FaceIndex,
    known_people: List[KnownPerson],
    min_confidence: float,
) -> Optional[MatchResult]:
    """
    Match a face embedding against known persons and return the best match
    if its confidence exceeds the threshold.

    Confidence is cosine similarity between L2-normalized embeddings.

    Parameters
    ----------
    embedding: List[float]
        Embedding of the detected face.
    index: _FaceIndex
        Index of known embeddings.
    known_people: List[KnownPerson]
        List of known persons (same order as embeddings in index).
    min_confidence: float
        Minimum confidence threshold to consider a match valid.

    Returns
    -------
    Optional[MatchResult]
        The best match if confidence >= min_confidence; otherwise None.
    """
    if np is None or not known_people or not index.ready():
        return None
    try:
        candidate = np.array(embedding, dtype="float32")
    except Exception:
        return None
    result = index.query(candidate, k=1)
    if result is None:
        return None
    match_id, confidence = result
    if confidence >= min_confidence and 0 <= match_id < len(known_people):
        kp = known_people[match_id]
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
        self._index = _FaceIndex()
        if np is not None and known_people:
            try:
                emb = np.vstack([np.asarray(kp.embedding, dtype="float32") for kp in known_people])
                emb = np.vstack([_l2_normalize(e) for e in emb])
                self._index.build(emb, list(range(len(known_people))))
            except Exception:
                self._index = _FaceIndex()
        # Deduplication cache: maps (status, identifier) to last event time
        self.dedup_cache: Dict[Tuple[str, str], datetime.datetime] = {}
        self._last_face_log: Optional[datetime.datetime] = None

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

    def process_faces(
        self,
        faces: List[Tuple[List[int], List[float]]],
        now_utc: datetime.datetime,
        mqtt_client: MQTTClient,
    ) -> List[FaceOverlay]:
        """Process precomputed face detections and embeddings."""
        if not self.global_config.enabled:
            return []
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=datetime.timezone.utc)
        timestamp_iso = now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        log_faces = os.getenv("PDS_FACE_LOG", "0") == "1"
        if log_faces:
            if self._last_face_log is None or (now_utc - self._last_face_log).total_seconds() >= 2:
                self.logger.info(
                    "Face detection: camera=%s faces=%d",
                    self.camera_id,
                    len(faces),
                )
                self._last_face_log = now_utc
        overlays: List[FaceOverlay] = []
        for bbox, embedding in faces:
            # Skip tiny faces that produce unreliable embeddings.
            min_face_size = int(os.getenv("PDS_FACE_MIN_SIZE", "60"))
            width = max(0, bbox[2] - bbox[0])
            height = max(0, bbox[3] - bbox[1])
            if width < min_face_size or height < min_face_size:
                continue
            zone_cfg = (self.camera_config.zone_id or "").strip().lower()
            if zone_cfg and zone_cfg not in {"all", "*"}:
                zone_id = self._determine_zone(bbox)
                if zone_id is None or zone_id != self.camera_config.zone_id:
                    continue
            if embedding is None:
                continue
            best_confidence = None
            best_match_id = None
            if np is not None and self.known_people and self._index.ready():
                try:
                    candidate = np.array(embedding, dtype="float32")
                    result = self._index.query(candidate, k=1)
                    if result is not None:
                        best_match_id, best_confidence = result
                except Exception:
                    best_match_id = None
                    best_confidence = None
            if best_confidence is None:
                self.logger.info(
                    "Face similarity: camera=%s zone=%s bbox=%s similarity=NA threshold=%.3f",
                    self.camera_id,
                    self.camera_config.zone_id,
                    bbox,
                    self.global_config.min_match_confidence,
                )
            else:
                self.logger.info(
                    "Face similarity: camera=%s zone=%s bbox=%s similarity=%.3f threshold=%.3f match_id=%s",
                    self.camera_id,
                    self.camera_config.zone_id,
                    bbox,
                    float(best_confidence),
                    self.global_config.min_match_confidence,
                    best_match_id,
                )
            match = match_face(
                embedding,
                self._index,
                self.known_people,
                self.global_config.min_match_confidence,
            )
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
            overlays.append(
                FaceOverlay(
                    bbox=bbox,
                    status=match_status,
                    person_id=person_id,
                    person_name=person_name,
                    confidence=confidence,
                )
            )
            if match_status == "UNKNOWN":
                if not self.camera_config.allow_unknown and self.global_config.unknown_event_enabled:
                    if log_faces:
                        self.logger.info(
                            "Face unknown: camera=%s zone=%s bbox=%s",
                            self.camera_id,
                            self.camera_config.zone_id,
                            bbox,
                        )
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
                    if log_faces:
                        self.logger.info(
                            "Face identified: camera=%s zone=%s person_id=%s name=%s role=%s conf=%.3f bbox=%s",
                            self.camera_id,
                            self.camera_config.zone_id,
                            person_id,
                            person_name,
                            person_role,
                            confidence,
                            bbox,
                        )
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
                    if log_faces:
                        self.logger.info(
                            "Face identified: camera=%s zone=%s person_id=%s name=%s role=%s conf=%.3f bbox=%s",
                            self.camera_id,
                            self.camera_config.zone_id,
                            person_id,
                            person_name,
                            person_role,
                            confidence,
                            bbox,
                        )
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
        return overlays

    def process_frame(
        self,
        frame: any,
        now_utc: datetime.datetime,
        mqtt_client: MQTTClient,
    ) -> List[FaceOverlay]:
        """
        Detect and recognize faces in the frame and publish events
        according to configured policies.
        """
        if frame is None:
            return []
        try:
            faces = detect_faces(frame)
        except Exception as exc:
            self.logger.exception("Face detection failed: %r", exc)
            return []
        return self.process_faces(faces, now_utc, mqtt_client)
