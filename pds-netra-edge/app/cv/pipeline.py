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
from typing import Callable, List, Tuple, Optional, Any
import logging
import os
import datetime
import cv2  # type: ignore
import time

from .yolo_detector import YoloDetector


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
    callback : Callable[[List[DetectedObject]], None]
        User-supplied callback invoked on each frame with the list of
        detected objects.
    frame_processors : Optional[List[Callable[[List[DetectedObject], datetime.datetime, Any], None]]]
        Additional handlers invoked per frame before the main callback.
    """

    def __init__(
        self,
        source: str,
        camera_id: str,
        detector: YoloDetector,
        callback: Callable[[List[DetectedObject]], None],
        stop_check: Optional[Callable[[], bool]] = None,
        frame_processors: Optional[List[Callable[[List[DetectedObject], datetime.datetime, Any], None]]] = None,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.source = source
        self.camera_id = camera_id
        self.detector = detector
        self.callback = callback
        self.stop_check = stop_check
        self.frame_processors = frame_processors or []

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
        debug_draw = os.getenv("PDS_DEBUG_DRAW", "0") == "1"
        debug_out = os.getenv("PDS_DEBUG_VIDEO_PATH", f"logs/debug_{self.camera_id}.mp4")
        writer = None
        try:
            self._rtsp_retry = 0
            
            while True:
                if self.stop_check and self.stop_check():
                    self.logger.info("Stopping pipeline for camera %s (source switch)", self.camera_id)
                    break
                # Initialize retry counter once
                if not hasattr(self, "_rtsp_retry"):
                    self._rtsp_retry = 0

                ret, frame = cap.read()

                if not ret:
                    self._rtsp_retry += 1

                    # Backoff strategy
                    if self._rtsp_retry == 1:
                        delay = 2
                    elif self._rtsp_retry == 2:
                        delay = 5
                    elif self._rtsp_retry == 3:
                        delay = 10
                    else:
                        delay = 30

                    self.logger.warning(
                        "RTSP stream ended for camera %s (attempt=%d, retry in %ds)",
                        self.camera_id,
                        self._rtsp_retry,
                        delay,
                    )

                    try:
                        cap.release()
                    except Exception:
                        pass

                    time.sleep(delay)

                    cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
                    if not cap.isOpened():
                        self.logger.warning("Reconnect failed (still offline): camera=%s", self.camera_id)
                        continue

                    continue

                # ✅ If frame received successfully, reset retry counter
                self._rtsp_retry = 0
                # Perform tracking using the detector's built-in tracker.
                tracked = self.detector.track(frame)
                # Convert to DetectedObject instances
                now_utc = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
                timestamp = now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")
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
                for processor in self.frame_processors:
                    try:
                        processor(objects, now_utc, frame)
                    except Exception as exc:
                        self.logger.exception("Frame processor error: %s", exc)
                # Invoke callback; if callback accepts a frame argument, pass it
                overlay_payload = None
                try:
                    # Try passing frame via keyword. This allows callbacks that accept
                    # an optional ``frame`` parameter to receive the raw image.
                    overlay_payload = self.callback(objects, frame=frame)
                except TypeError:
                    # Fallback for callbacks that only accept the list of objects
                    overlay_payload = self.callback(objects)
                except Exception as exc:
                    self.logger.exception("Callback raised exception: %s", exc)
                if debug_draw:
                    if writer is None:
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        if not fps or fps <= 0:
                            fps = 15.0
                        height, width = frame.shape[:2]
                        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                        writer = cv2.VideoWriter(debug_out, fourcc, fps, (width, height))
                        if not writer.isOpened():
                            self.logger.error("Failed to open debug video writer at %s", debug_out)
                            writer = None
                    for track_id, (cls_name, conf, bbox) in tracked:
                        x1, y1, x2, y2 = bbox
                        label = f"{cls_name} {conf:.2f} id={track_id}"
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 180, 255), 2)
                        cv2.putText(
                            frame,
                            label,
                            (x1, max(10, y1 - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (0, 180, 255),
                            2,
                            cv2.LINE_AA,
                        )
                    if isinstance(overlay_payload, dict):
                        faces = overlay_payload.get("faces") or []
                        for face in faces:
                            if isinstance(face, dict):
                                bbox = face.get("bbox")
                                status = face.get("status")
                                name = face.get("person_name")
                                conf = face.get("confidence")
                            else:
                                bbox = getattr(face, "bbox", None)
                                status = getattr(face, "status", None)
                                name = getattr(face, "person_name", None)
                                conf = getattr(face, "confidence", None)
                            if not bbox or status is None:
                                continue
                            x1, y1, x2, y2 = bbox
                            color = (0, 200, 0) if status == "KNOWN" else (0, 0, 255)
                            label = f"{name or status} {float(conf or 0.0):.2f}"
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                            cv2.putText(
                                frame,
                                label,
                                (x1, max(10, y1 - 5)),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.7,
                                color,
                                2,
                                cv2.LINE_AA,
                            )
                    if writer is not None:
                        writer.write(frame)
        finally:
            if writer is not None:
                writer.release()
            cap.release()
            self.logger.info("Pipeline for camera %s stopped", self.camera_id)
