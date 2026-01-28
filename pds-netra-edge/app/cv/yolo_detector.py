"""
Wrapper around the Ultralytics YOLO model for object detection.
"""

from __future__ import annotations

from typing import List, Tuple, Optional
import logging

try:
    from ultralytics import YOLO  # type: ignore
except ImportError:
    YOLO = None  # type: ignore


class YoloDetector:
    """
    YOLO detector wrapper for performing object detection on frames.
    """

    def __init__(
        self,
        model_name: str = "animal.pt",
        device: str = "cpu",
        tracker_name: str = "bytetrack.yaml",
        track_persist: bool = True,
        track_conf: float | None = None,
        track_iou: float | None = None,
        conf: float | None = None,
        iou: float | None = None,
        imgsz: int | None = None,
        classes: list[int] | None = None,
        max_det: int | None = None,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        if YOLO is None:
            raise RuntimeError("ultralytics is not installed; please install ultralytics")

        self.device = device
        self.tracker_name = tracker_name
        self.track_persist = track_persist
        self.track_conf = track_conf
        self.track_iou = track_iou
        self.conf = conf
        self.iou = iou
        self.imgsz = imgsz
        self.classes = classes
        self.max_det = max_det
        # Load the model. We defer device placement until inference time.
        self.model = YOLO(model_name)
        self.names = self.model.names
        self.logger.info(
            "Loaded YOLO model=%s device=%s conf=%s iou=%s imgsz=%s classes=%s max_det=%s",
            model_name,
            device,
            self.conf,
            self.iou,
            self.imgsz,
            self.classes,
            self.max_det,
        )

    def detect(self, frame) -> List[Tuple[str, float, List[int]]]:
        """
        Returns list of (class_name, confidence, [x1,y1,x2,y2])
        """
        # Use predict() so kwargs are consistently supported
        results = self.model.predict(
            source=frame,
            device=self.device,
            conf=self.conf,
            iou=self.iou,
            imgsz=self.imgsz,
            classes=self.classes,
            max_det=self.max_det,
            verbose=False,
        )[0]

        detections: List[Tuple[str, float, List[int]]] = []
        for box in results.boxes:
            class_id = int(box.cls.item())
            class_name = self.names.get(class_id, str(class_id))
            confidence = float(box.conf.item())
            xyxy = box.xyxy.tolist()[0] 
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

