"""
Wrapper around the Ultralytics YOLO model for object detection.

This class hides the details of loading the model and running inference
on individual frames. The default model name can be overridden via
configuration. At runtime you should ensure that the appropriate model
weights are available locally. See https://github.com/ultralytics/ultralytics
for details on supported models.
"""

from __future__ import annotations

from typing import List, Tuple
import logging
try:
    # Import ultralytics at runtime. This may throw if the package is not
    # installed; catching here allows graceful degradation in unit tests.
    from ultralytics import YOLO  # type: ignore
except ImportError:
    YOLO = None  # type: ignore


class YoloDetector:
    """
    YOLO detector wrapper for performing object detection on frames.

    Parameters
    ----------
    model_name : str
        Path to a YOLO weights file or model name to load. Defaults to
        ``best.pt`` which is a small model suitable for CPU inference.
    device : str
        Device to run inference on. Use ``"cpu"`` for CPU-only hosts or
        ``"cuda"`` when running on NVIDIA GPUs.
    """

    def __init__(
        self,
        model_name: str = "animal.pt",
        device: str = "cpu",
        tracker_name: str = "bytetrack.yaml",
        track_persist: bool = True,
        track_conf: float | None = None,
        track_iou: float | None = None,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        if YOLO is None:
            raise RuntimeError(
                "ultralytics package is not installed; please install ultralytics to use YoloDetector"
            )
        self.device = device
        self.tracker_name = tracker_name
        self.track_persist = track_persist
        self.track_conf = track_conf
        self.track_iou = track_iou
        # Load the model. We defer device placement until inference time.
        self.model = YOLO(model_name)
        self.names = self.model.names  # class names
        self.logger.info("Loaded YOLO model %s on device %s", model_name, device)

    def detect(self, frame) -> List[Tuple[str, float, List[int]]]:
        """
        Run object detection on a single frame.

        Parameters
        ----------
        frame: numpy.ndarray
            Image in BGR format as returned by ``cv2.VideoCapture.read``.

        Returns
        -------
        List[Tuple[str, float, List[int]]]
            A list of tuples containing (class_name, confidence, bbox)
            where ``bbox`` is in [x1, y1, x2, y2] pixel coordinates.
        """
        results = self.model(frame, device=self.device)[0]
        detections: List[Tuple[str, float, List[int]]] = []
        for box in results.boxes:
            class_id = int(box.cls.item())
            class_name = self.names.get(class_id, str(class_id))
            confidence = float(box.conf.item())
            xyxy = box.xyxy.tolist()[0]  # type: ignore
            bbox = [int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])]
            detections.append((class_name, confidence, bbox))
        return detections

    def track(self, frame) -> List[Tuple[int, Tuple[str, float, List[int]]]]:
        """
        Run ByteTrack-based tracking on a single frame.

        Returns
        -------
        List[Tuple[int, Tuple[str, float, List[int]]]]
            A list of tuples containing (track_id, (class_name, confidence, bbox))
            where ``bbox`` is in [x1, y1, x2, y2] pixel coordinates.
        """
        track_kwargs = {
            "device": self.device,
            "persist": self.track_persist,
            "tracker": self.tracker_name,
            "verbose": False,
        }
        if self.track_conf is not None:
            track_kwargs["conf"] = self.track_conf
        if self.track_iou is not None:
            track_kwargs["iou"] = self.track_iou
        results = self.model.track(
            frame,
            **track_kwargs,
        )[0]
        tracked: List[Tuple[int, Tuple[str, float, List[int]]]] = []
        for box in results.boxes:
            class_id = int(box.cls.item())
            class_name = self.names.get(class_id, str(class_id))
            confidence = float(box.conf.item()) if box.conf is not None else 0.0
            xyxy = box.xyxy.tolist()[0]  # type: ignore
            bbox = [int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])]
            if box.id is None:
                track_id = -1
            else:
                track_id = int(box.id.item())
            tracked.append((track_id, (class_name, confidence, bbox)))
        return tracked

