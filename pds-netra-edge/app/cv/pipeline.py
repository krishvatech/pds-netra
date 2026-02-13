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
import threading

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
        latest_frame_hook: Optional[Callable[[Any, float], None]] = None,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.source = source
        self.camera_id = camera_id
        self.detector = detector
        self.callback = callback
        self.stop_check = stop_check
        self.frame_processors = frame_processors or []
        self.latest_frame_hook = latest_frame_hook

    @staticmethod
    def _is_realtime_source(source: str) -> bool:
        s = (source or "").strip().lower()
        return s.startswith(("rtsp://", "rtsps://", "http://", "https://"))

    @staticmethod
    def _env_true(name: str, default: str = "false") -> bool:
        return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}

    @staticmethod
    def _reconnect_delay(attempt: int) -> int:
        if attempt <= 1:
            return 2
        if attempt == 2:
            return 5
        if attempt == 3:
            return 10
        return 30

    def _apply_capture_tuning(self, cap: Any, *, realtime_source: bool) -> None:
        if not realtime_source:
            return
        try:
            buffer_size = int(os.getenv("EDGE_RTSP_CAPTURE_BUFFER", "1"))
        except Exception:
            buffer_size = 1
        if buffer_size > 0:
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, buffer_size)
            except Exception:
                pass

    def _open_capture(self, *, realtime_source: bool) -> Any:
        if realtime_source:
            # Lower FFmpeg demux/decode latency if options were not set externally.
            os.environ.setdefault(
                "OPENCV_FFMPEG_CAPTURE_OPTIONS",
                "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|max_delay;0|reorder_queue_size;0",
            )
            cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                cap = cv2.VideoCapture(self.source)
        else:
            cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            return None
        self._apply_capture_tuning(cap, realtime_source=realtime_source)
        return cap

    def run(self) -> None:
        """
        Execute the pipeline loop until the video source is exhausted.

        This method opens the video capture source, processes each frame
        sequentially and invokes the callback with detected objects.
        """
        self.logger.info("Starting pipeline for camera %s", self.camera_id)
        realtime_source = self._is_realtime_source(self.source)
        latest_frame_mode = realtime_source and self._env_true("EDGE_LIVE_LATEST_FRAME_MODE", "true")

        cap = self._open_capture(realtime_source=realtime_source)
        if cap is None:
            self.logger.error("Unable to open video source: %s", self.source)
            return
        debug_draw = os.getenv("PDS_DEBUG_DRAW", "0") == "1"
        debug_out = os.getenv("PDS_DEBUG_VIDEO_PATH", f"logs/debug_{self.camera_id}.mp4")
        writer = None
        fps_hint = cap.get(cv2.CAP_PROP_FPS)
        if not fps_hint or fps_hint <= 0:
            fps_hint = 15.0
        try:
            def process_frame(frame: Any, frame_ts: Optional[float] = None) -> None:
                nonlocal writer
                tracked = self.detector.track(frame)
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
                    overlay_payload = self.callback(objects, frame=frame, frame_ts=frame_ts)
                except TypeError:
                    try:
                        overlay_payload = self.callback(objects, frame=frame)
                    except TypeError:
                        # Fallback for callbacks that only accept the list of objects
                        overlay_payload = self.callback(objects)
                except Exception as exc:
                    self.logger.exception("Callback raised exception: %s", exc)
                if debug_draw:
                    if writer is None:
                        height, width = frame.shape[:2]
                        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                        writer = cv2.VideoWriter(debug_out, fourcc, fps_hint, (width, height))
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

            if latest_frame_mode:
                frame_cond = threading.Condition()
                capture_stop = threading.Event()
                latest_frame: Optional[Any] = None
                latest_frame_ts: Optional[float] = None
                latest_seq = 0
                self._rtsp_retry = 0

                def capture_loop() -> None:
                    nonlocal cap, latest_frame, latest_frame_ts, latest_seq
                    while not capture_stop.is_set():
                        if cap is None or not cap.isOpened():
                            cap = self._open_capture(realtime_source=realtime_source)
                            if cap is None:
                                self._rtsp_retry += 1
                                delay = self._reconnect_delay(self._rtsp_retry)
                                self.logger.warning(
                                    "Reconnect failed for camera=%s (attempt=%d, retry in %ds)",
                                    self.camera_id,
                                    self._rtsp_retry,
                                    delay,
                                )
                                capture_stop.wait(timeout=delay)
                                continue
                            self._rtsp_retry = 0

                        ret, frame = cap.read()
                        if not ret:
                            self._rtsp_retry += 1
                            delay = self._reconnect_delay(self._rtsp_retry)
                            self.logger.warning(
                                "RTSP read failed for camera=%s (attempt=%d, retry in %ds)",
                                self.camera_id,
                                self._rtsp_retry,
                                delay,
                            )
                            try:
                                cap.release()
                            except Exception:
                                pass
                            cap = None
                            capture_stop.wait(timeout=delay)
                            continue

                        capture_ts = time.time()
                        self._rtsp_retry = 0
                        with frame_cond:
                            latest_frame = frame
                            latest_frame_ts = capture_ts
                            latest_seq += 1
                            frame_cond.notify_all()
                        if self.latest_frame_hook is not None:
                            try:
                                self.latest_frame_hook(frame, capture_ts)
                            except Exception as exc:
                                self.logger.debug("latest_frame_hook failed for camera %s: %s", self.camera_id, exc)

                capture_thread = threading.Thread(
                    target=capture_loop,
                    name=f"Capture-{self.camera_id}",
                    daemon=True,
                )
                capture_thread.start()

                last_seen_seq = 0
                while True:
                    if self.stop_check and self.stop_check():
                        self.logger.info("Stopping pipeline for camera %s (source switch)", self.camera_id)
                        break
                    with frame_cond:
                        if latest_seq == last_seen_seq:
                            frame_cond.wait(timeout=1.0)
                        if latest_seq == last_seen_seq:
                            continue
                        last_seen_seq = latest_seq
                        frame = latest_frame.copy() if latest_frame is not None else None
                        frame_ts = latest_frame_ts
                    if frame is None:
                        continue
                    process_frame(frame, frame_ts=frame_ts)

                capture_stop.set()
                with frame_cond:
                    frame_cond.notify_all()
                capture_thread.join(timeout=5)
            else:
                self._rtsp_retry = 0
                while True:
                    if self.stop_check and self.stop_check():
                        self.logger.info("Stopping pipeline for camera %s (source switch)", self.camera_id)
                        break

                    ret, frame = cap.read()
                    if not ret:
                        self._rtsp_retry += 1
                        delay = self._reconnect_delay(self._rtsp_retry)
                        self.logger.warning(
                            "RTSP stream ended for camera %s (attempt=%d, retry in %ds)",
                            self.camera_id,
                            self._rtsp_retry,
                            delay,
                        )
                        try:
                            cap.release()
                        except Exception as exc:
                            self.logger.warning("Failed to release capture for camera %s: %s", self.camera_id, exc)
                        time.sleep(delay)
                        cap = self._open_capture(realtime_source=realtime_source)
                        if cap is None:
                            self.logger.warning("Reconnect failed (still offline): camera=%s", self.camera_id)
                            continue
                        self._rtsp_retry = 0
                        continue

                    capture_ts = time.time()
                    self._rtsp_retry = 0
                    if realtime_source and self.latest_frame_hook is not None:
                        try:
                            self.latest_frame_hook(frame, capture_ts)
                        except Exception as exc:
                            self.logger.debug("latest_frame_hook failed for camera %s: %s", self.camera_id, exc)
                    process_frame(frame, frame_ts=capture_ts)
        finally:
            if writer is not None:
                writer.release()
            if cap is not None:
                cap.release()
            self.logger.info("Pipeline for camera %s stopped", self.camera_id)
