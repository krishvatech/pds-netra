"""
Annotated video writer for test runs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Tuple
import time

try:
    import cv2  # type: ignore
except ImportError:
    cv2 = None  # type: ignore


class AnnotatedVideoWriter:
    """Writes an annotated MP4 with bounding boxes and labels."""

    def __init__(
        self,
        output_path: str,
        fps: float = 15.0,
        latest_path: Optional[str] = None,
        latest_interval: float = 0.2,
    ) -> None:
        self.output_path = Path(output_path)
        self.fps = fps
        self.latest_path = Path(latest_path) if latest_path else None
        self.latest_interval = latest_interval
        self._last_latest_ts = 0.0
        self._writer = None
        self._size: Optional[Tuple[int, int]] = None
        self._frames_written = 0

    def _ensure_writer(self, frame) -> bool:
        if cv2 is None:
            return False
        if self._writer is not None:
            return True
        height, width = frame.shape[:2]
        self._size = (width, height)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        for codec in ("avc1", "mp4v"):
            fourcc = cv2.VideoWriter_fourcc(*codec)
            writer = cv2.VideoWriter(str(self.output_path), fourcc, self.fps, self._size)
            if writer.isOpened():
                self._writer = writer
                return True
        return False

    def write_frame(
        self,
        frame,
        detections: Sequence[Tuple[str, float, Sequence[int]]],
    ) -> None:
        if cv2 is None:
            return
        if not self._ensure_writer(frame):
            return
        canvas = frame.copy()
        for class_name, confidence, bbox in detections:
            x1, y1, x2, y2 = bbox
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 200, 255), 2)
            label = f"{class_name} {confidence:.2f}"
            cv2.putText(
                canvas,
                label,
                (x1, max(y1 - 6, 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 200, 255),
                1,
                cv2.LINE_AA,
            )
        self._writer.write(canvas)
        self._frames_written += 1
        if self.latest_path is not None:
            now = time.monotonic()
            if now - self._last_latest_ts >= self.latest_interval:
                self.latest_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    import os
                    tmp_path = self.latest_path.with_suffix(".tmp")
                    cv2.imwrite(str(tmp_path), canvas)
                    os.replace(str(tmp_path), str(self.latest_path))
                except Exception:
                    pass
                self._last_latest_ts = now

    def close(self) -> None:
        if self._writer is not None:
            self._writer.release()
            self._writer = None

    def frames_written(self) -> int:
        return self._frames_written


class LiveFrameWriter:
    """Writes a periodically updated annotated frame for live viewing."""

    def __init__(self, latest_path: str, latest_interval: float = 0.2) -> None:
        self.latest_path = Path(latest_path)
        self.latest_interval = latest_interval
        self._last_latest_ts = 0.0

    def write_frame(
        self,
        frame,
        detections: Sequence[Tuple[str, float, Sequence[int]]],
    ) -> None:
        if cv2 is None:
            return
        now = time.monotonic()
        if now - self._last_latest_ts < self.latest_interval:
            return
        canvas = frame.copy()
        for class_name, confidence, bbox in detections:
            x1, y1, x2, y2 = bbox
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 200, 255), 2)
            label = f"{class_name} {confidence:.2f}"
            cv2.putText(
                canvas,
                label,
                (x1, max(y1 - 6, 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 200, 255),
                1,
                cv2.LINE_AA,
            )
        self.latest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import os
            tmp_path = self.latest_path.with_suffix(".tmp")
            cv2.imwrite(str(tmp_path), canvas)
            os.replace(str(tmp_path), str(self.latest_path))
        except Exception:
            pass
        self._last_latest_ts = now
