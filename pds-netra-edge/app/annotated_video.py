"""
Annotated video writer for test runs.

Windows note:
- The Dashboard/Backend may read *_latest.jpg while the Edge writes it.
- On Windows this can throw PermissionError / WinError 5 (file locking).
- We fix it by writing to a temp file and using os.replace() with retries.
- Also: DO NOT block _latest.jpg updates if MP4 VideoWriter fails to open.
"""

from __future__ import annotations

from pathlib import Path
import logging
from typing import Optional, Sequence, Tuple
import time

try:
    import cv2  # type: ignore
except ImportError:
    cv2 = None  # type: ignore


_LOG = logging.getLogger("annotated_video")


def _atomic_write_jpg(latest_path: Path, image_bgr, retries: int = 6, delay: float = 0.02) -> bool:
    if cv2 is None:
        return False

    try:
        ok, encoded = cv2.imencode(".jpg", image_bgr)
        if not ok:
            return False
        data = encoded.tobytes()
    except Exception:
        return False

    latest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = latest_path.with_suffix(latest_path.suffix + ".tmp")

    import os

    for _ in range(max(1, retries)):
        try:
            with open(tmp_path, "wb") as f:
                f.write(data)
            os.replace(str(tmp_path), str(latest_path))
            return True
        except PermissionError:
            time.sleep(delay)
        except OSError:
            time.sleep(delay)
        except Exception:
            try:
                if tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
            return False
    return False


class AnnotatedVideoWriter:
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
            try:
                fourcc = cv2.VideoWriter_fourcc(*codec)
                writer = cv2.VideoWriter(str(self.output_path), fourcc, self.fps, self._size)
                if writer.isOpened():
                    self._writer = writer
                    _LOG.info("AnnotatedVideoWriter: opened video writer codec=%s path=%s", codec, self.output_path)
                    return True
            except Exception:
                continue

        _LOG.warning(
            "AnnotatedVideoWriter: could not open MP4 writer for %s (will still write latest JPG)",
            self.output_path,
        )
        return False

    def write_frame(
        self,
        frame,
        detections: Sequence[Tuple[str, float, Sequence[int], Optional[int]]],
    ) -> None:
        if cv2 is None:
            return

        canvas = frame.copy()

        for class_name, confidence, bbox, track_id in detections:
            x1, y1, x2, y2 = bbox
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 200, 255), 2)
            label = f"{class_name} {confidence:.2f}"
            # ✅ FIX: track_id can be None
            if track_id is not None and track_id >= 0:
                label = f"{label} id={track_id}"
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

        if self.latest_path is not None:
            now = time.monotonic()
            if now - self._last_latest_ts >= self.latest_interval:
                try:
                    _atomic_write_jpg(self.latest_path, canvas, retries=6, delay=0.02)
                except Exception:
                    pass
                self._last_latest_ts = now

        if self._ensure_writer(frame) and self._writer is not None:
            try:
                self._writer.write(canvas)
                self._frames_written += 1
            except Exception:
                _LOG.exception("AnnotatedVideoWriter: video write failed; disabling MP4 writer for this run")
                try:
                    self._writer.release()
                except Exception:
                    pass
                self._writer = None

    def close(self) -> None:
        if self._writer is not None:
            try:
                self._writer.release()
            except Exception:
                pass
            self._writer = None

    def frames_written(self) -> int:
        return self._frames_written


class LiveFrameWriter:
    def __init__(self, latest_path: str, latest_interval: float = 0.2) -> None:
        self.latest_path = Path(latest_path)
        self.latest_interval = latest_interval
        self._last_latest_ts = 0.0
        self._log = logging.getLogger("live_frame_writer")

    def write_frame(
        self,
        frame,
        detections: Sequence[Tuple[str, float, Sequence[int], Optional[int]]],
    ) -> None:
        if cv2 is None:
            return

        now = time.monotonic()
        if now - self._last_latest_ts < self.latest_interval:
            return

        canvas = frame.copy()
        for class_name, confidence, bbox, track_id in detections:
            x1, y1, x2, y2 = bbox
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 200, 255), 2)
            label = f"{class_name} {confidence:.2f}"
            # ✅ FIX: track_id can be None
            if track_id is not None and track_id >= 0:
                label = f"{label} id={track_id}"
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

        try:
            ok = _atomic_write_jpg(self.latest_path, canvas, retries=6, delay=0.02)
            if not ok:
                self._log.warning("Failed to write live frame to %s", self.latest_path)
        except Exception:
            self._log.exception("Failed to write live frame to %s", self.latest_path)

        self._last_latest_ts = now
