"""
Watchlist matching processor for camera frames.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..events.mqtt_client import MQTTClient
from ..schemas.watchlist import FaceMatchEvent, FaceMatchPayload, FaceMatchCandidate, FaceMatchEvidence
from .manager import WatchlistManager
from ..cv.zones import is_bbox_in_zone
from ..core.errors import log_exception


@dataclass
class WatchlistMatch:
    person_id: str
    person_name: str
    match_score: float
    embedding_hash: str


class WatchlistProcessor:
    def __init__(
        self,
        *,
        camera_id: str,
        godown_id: str,
        manager: WatchlistManager,
        min_confidence: float,
        cooldown_seconds: int,
        zone_polygons: Optional[Dict[str, List[Tuple[int, int]]]] = None,
        zone_enforce: bool = False,
        http_fallback: bool = False,
    ) -> None:
        self.logger = logging.getLogger(f"Watchlist-{camera_id}")
        self.camera_id = camera_id
        self.godown_id = godown_id
        self.manager = manager
        self.min_confidence = min_confidence
        self.cooldown_seconds = max(1, int(cooldown_seconds))
        self.http_fallback = http_fallback
        self.zone_polygons = zone_polygons or {}
        self.zone_enforce = zone_enforce
        self._last_alert: Dict[Tuple[str, str], datetime.datetime] = {}

    def _cooldown_ok(self, person_id: str, now: datetime.datetime) -> bool:
        key = (self.camera_id, person_id)
        last = self._last_alert.get(key)
        if last and (now - last).total_seconds() < self.cooldown_seconds:
            return False
        self._last_alert[key] = now
        return True

    def process_faces(
        self,
        faces: List[Tuple[List[int], List[float]]],
        now_utc: datetime.datetime,
        mqtt_client: MQTTClient,
        snapshotter=None,
        frame=None,
    ) -> None:
        if not faces:
            return
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=datetime.timezone.utc)
        timestamp_iso = now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")

        for bbox, embedding in faces:
            if self.zone_enforce and self.zone_polygons and not self._bbox_in_any_zone(bbox):
                continue
            match = self._match_face(embedding)
            if not match:
                continue
            if match.match_score < self.min_confidence:
                continue
            if not self._cooldown_ok(match.person_id, now_utc):
                continue
            event_id = str(uuid.uuid4())
            snapshot_url = None
            local_path = None
            if snapshotter is not None and frame is not None:
                try:
                    snapshot_url = snapshotter(frame, event_id, now_utc, bbox=bbox, label=match.person_name)
                    local_path = snapshot_url if snapshot_url and snapshot_url.startswith("/") else None
                except Exception as exc:
                    log_exception(
                        self.logger,
                        "Watchlist snapshot failed",
                        extra={"camera_id": self.camera_id, "person_id": match.person_id},
                        exc=exc,
                    )
                    snapshot_url = None
                    local_path = None
            payload = FaceMatchPayload(
                person_candidate=FaceMatchCandidate(
                    embedding_hash=match.embedding_hash,
                    match_score=match.match_score,
                    is_blacklisted=True,
                    blacklist_person_id=match.person_id,
                ),
                evidence=FaceMatchEvidence(
                    snapshot_url=snapshot_url,
                    local_snapshot_path=local_path,
                    bbox=bbox,
                    frame_ts=timestamp_iso,
                ),
            )
            event = FaceMatchEvent(
                event_id=event_id,
                occurred_at=timestamp_iso,
                godown_id=self.godown_id,
                camera_id=self.camera_id,
                payload=payload,
                correlation_id=str(uuid.uuid4()),
            )
            mqtt_client.publish_face_match(event, http_fallback=self.http_fallback)
            self.logger.warning(
                "Watchlist match: person=%s camera=%s score=%.3f",
                match.person_id,
                self.camera_id,
                match.match_score,
            )

    def _bbox_in_any_zone(self, bbox: List[int]) -> bool:
        for polygon in self.zone_polygons.values():
            if is_bbox_in_zone(bbox, polygon):
                return True
        return False

    def _match_face(self, embedding: List[float]) -> Optional[WatchlistMatch]:
        result = self.manager.match(embedding)
        if result is None:
            return None
        entry, score, emb_hash = result
        return WatchlistMatch(
            person_id=entry.person_id,
            person_name=entry.name,
            match_score=score,
            embedding_hash=emb_hash,
        )
