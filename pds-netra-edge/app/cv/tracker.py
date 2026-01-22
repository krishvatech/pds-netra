"""
Simple object tracker abstraction.

This module provides a lightweight IoU-based tracker that assigns stable
IDs across frames. It is not a full multi-object tracker, but it is
enough to reduce per-frame ID churn for detections. In production you
should replace this implementation with a more sophisticated tracker
such as ByteTrack or DeepSORT.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple
import itertools


@dataclass
class Track:
    """Tracks a single object across frames."""

    track_id: int
    class_name: str
    confidence: float
    bbox: List[int]
    age: int = 0
    hits: int = 0


def _iou(box_a: List[int], box_b: List[int]) -> float:
    """Compute intersection-over-union for two [x1, y1, x2, y2] boxes."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


class SimpleTracker:
    """
    Assigns stable track IDs using a greedy IoU match per frame.
    """

    def __init__(self, max_age: int = 5, iou_threshold: float = 0.3) -> None:
        # unique id generator
        self._id_iter = itertools.count(start=1)
        self.max_age = max_age
        self.iou_threshold = iou_threshold
        self._tracks: List[Track] = []

    def update(self, detections: List[Tuple[str, float, List[int]]]) -> List[Tuple[int, Tuple[str, float, List[int]]]]:
        """
        Assign track IDs to detections using IoU matching.

        Parameters
        ----------
        detections : List[Tuple[str, float, List[int]]]
            List of raw detection tuples (class_name, confidence, bbox).

        Returns
        -------
        List[Tuple[int, Tuple[str, float, List[int]]]]
            List of (track_id, detection) tuples.
        """
        if not detections:
            for track in self._tracks:
                track.age += 1
            self._tracks = [track for track in self._tracks if track.age <= self.max_age]
            return []

        assigned: List[int | None] = [None] * len(detections)
        candidates: List[Tuple[float, int, int]] = []
        for t_idx, track in enumerate(self._tracks):
            for d_idx, (cls_name, _conf, bbox) in enumerate(detections):
                if track.class_name.lower() != str(cls_name).lower():
                    continue
                iou = _iou(track.bbox, bbox)
                if iou >= self.iou_threshold:
                    candidates.append((iou, t_idx, d_idx))
        candidates.sort(key=lambda item: item[0], reverse=True)

        used_tracks: set[int] = set()
        used_dets: set[int] = set()
        for _iou_score, t_idx, d_idx in candidates:
            if t_idx in used_tracks or d_idx in used_dets:
                continue
            used_tracks.add(t_idx)
            used_dets.add(d_idx)
            cls_name, conf, bbox = detections[d_idx]
            track = self._tracks[t_idx]
            track.class_name = cls_name
            track.confidence = conf
            track.bbox = bbox
            track.age = 0
            track.hits += 1
            assigned[d_idx] = track.track_id

        for d_idx, (cls_name, conf, bbox) in enumerate(detections):
            if assigned[d_idx] is not None:
                continue
            track_id = next(self._id_iter)
            self._tracks.append(
                Track(
                    track_id=track_id,
                    class_name=cls_name,
                    confidence=conf,
                    bbox=bbox,
                    age=0,
                    hits=1,
                )
            )
            assigned[d_idx] = track_id

        active_ids = set(assigned)
        for track in self._tracks:
            if track.track_id not in active_ids:
                track.age += 1
        self._tracks = [track for track in self._tracks if track.age <= self.max_age]

        tracked: List[Tuple[int, Tuple[str, float, List[int]]]] = []
        for det_idx, det in enumerate(detections):
            tracked.append((int(assigned[det_idx]), det))
        return tracked
