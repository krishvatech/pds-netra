"""
Generic computer vision pipeline for PDS Netra.

The pipeline reads frames from a video source (RTSP stream or local file),
performs object detection using a detector, applies tracking and
packages results into a list of ``DetectedObject`` instances. A user-provided
callback is invoked for each frame with the detection results. This
callback can implement custom logic such as rule evaluation or event
publishing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Tuple
import logging
import datetime
import cv2  # type: ignore

from .yolo_detector import YoloDetector
from .tracker import SimpleTracker


@dataclass
class DetectedObject:
    """Representation of a detected and tracked object in a frame."""

    camera_id: str
    class_name: str
    confidence: float
    bbox: List[int]
    track_id: int
    timestamp_utc: str


class Pipeline:
    """
    Video processing pipeline that performs detection and tracking on frames.

    Parameters
    ----------
    source : str
        RTSP URL or local file path for the video source.
    camera_id : str
        Identifier for the camera.
    detector : YoloDetector
        Detector instance used to perform object detection.
    tracker : SimpleTracker
        Tracker instance used to assign track IDs to detections.
    callback : Callable[[List[DetectedObject]], None]
        User-supplied callback invoked on each frame with the list of
        detected objects.
    """

    def __init__(
        self,
        source: str,
        camera_id: str,
        detector: YoloDetector,
        tracker: SimpleTracker,
        callback: Callable[[List[DetectedObject]], None],
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.source = source
        self.camera_id = camera_id
        self.detector = detector
        self.tracker = tracker
        self.callback = callback

    def run(self) -> None:
        """
        Execute the pipeline loop until the video source is exhausted.

        This method opens the video capture source, processes each frame
        sequentially and invokes the callback with detected objects.
        """
        self.logger.info("Starting pipeline for camera %s", self.camera_id)
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            self.logger.error("Unable to open video source: %s", self.source)
            return
        try:
            while True:
                ret, frame = cap.read()
                if not ret or frame is None:
                    self.logger.info("End of stream for camera %s", self.camera_id)
                    break
                # Perform detection
                detections = self.detector.detect(frame)
                # Assign track IDs
                tracked = self.tracker.update(detections)
                # Convert to DetectedObject instances
                timestamp = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
                objects: List[DetectedObject] = []
                for track_id, (cls_name, conf, bbox) in tracked:
                    obj = DetectedObject(
                        camera_id=self.camera_id,
                        class_name=cls_name,
                        confidence=conf,
                        bbox=bbox,
                        track_id=track_id,
                        timestamp_utc=timestamp,
                    )
                    objects.append(obj)
                # Invoke callback; if callback accepts a frame argument, pass it
                try:
                    # Try passing frame via keyword. This allows callbacks that accept
                    # an optional ``frame`` parameter to receive the raw image.
                    self.callback(objects, frame=frame)
                except TypeError:
                    # Fallback for callbacks that only accept the list of objects
                    self.callback(objects)
                except Exception as exc:
                    self.logger.exception("Callback raised exception: %s", exc)
        finally:
            cap.release()
            self.logger.info("Pipeline for camera %s stopped", self.camera_id)