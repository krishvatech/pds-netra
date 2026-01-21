"""
Simple object tracker abstraction.

This module provides a very naive object tracker that assigns a unique
identifier to each detection. It does not implement temporal
association between frames. In production you should replace this
implementation with a more sophisticated tracker such as ByteTrack or
DeepSORT.
"""

from __future__ import annotations

from typing import List, Tuple
import itertools


class SimpleTracker:
    """
    Assigns incremental track IDs to detected objects without temporal
    association. This is a placeholder and should be replaced with an
    actual tracker for real deployments.
    """

    def __init__(self) -> None:
        # unique id generator
        self._id_iter = itertools.count(start=1)

    def update(self, detections: List[Tuple[str, float, List[int]]]) -> List[Tuple[int, Tuple[str, float, List[int]]]]:
        """
        Assign track IDs to detections.

        Parameters
        ----------
        detections : List[Tuple[str, float, List[int]]]
            List of raw detection tuples (class_name, confidence, bbox).

        Returns
        -------
        List[Tuple[int, Tuple[str, float, List[int]]]]
            List of (track_id, detection) tuples.
        """
        tracked: List[Tuple[int, Tuple[str, float, List[int]]]] = []
        for det in detections:
            track_id = next(self._id_iter)
            tracked.append((track_id, det))
        return tracked