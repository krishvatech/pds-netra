"""
ANPR (Automatic Number Plate Recognition) utilities for PDS Netra.

This module provides classes and functions to detect and recognize
vehicle number plates using a detection model and an OCR engine. It
also includes a processor that evaluates ANPR-specific rules and
emits events via MQTT.
"""

from __future__ import annotations

import logging
import datetime
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

try:
    import cv2  # type: ignore
except ImportError:
    cv2 = None  # type: ignore

try:
    from paddleocr import PaddleOCR  # type: ignore
except ImportError:
    PaddleOCR = None  # type: ignore

from zoneinfo import ZoneInfo

from .yolo_detector import YoloDetector
from .zones import is_bbox_in_zone
from ..models.event import EventModel, MetaModel
import uuid
from ..events.mqtt_client import MQTTClient
from ..rules.loader import (
    AnprMonitorRule,
    AnprWhitelistRule,
    AnprBlacklistRule,
    BaseRule,
)


@dataclass
class RecognizedPlate:
    """Representation of a recognized number plate in a frame."""

    camera_id: str
    bbox: List[int]
    plate_text: str
    confidence: float
    timestamp_utc: str


class PlateDetector:
    """
    Simple wrapper around a YOLO detector for detecting license plates.

    Parameters
    ----------
    detector: YoloDetector
        The underlying YOLO detector instance used for inference.
    plate_class_names: List[str]
        Names of classes in the detector corresponding to number plates.
        Defaults to ["license_plate"].
    """

    def __init__(self, detector: YoloDetector, plate_class_names: Optional[List[str]] = None) -> None:
        self.detector = detector
        # Accept multiple names; lower-case for comparison
        if plate_class_names is None:
            plate_class_names = ["license_plate"]
        self.plate_class_names = {name.lower() for name in plate_class_names}

    def detect_plates(self, frame: Any) -> List[Tuple[str, float, List[int]]]:
        """
        Detect number plates in a frame.

        Parameters
        ----------
        frame: numpy.ndarray
            Image in BGR format.

        Returns
        -------
        List of tuples (class_name, confidence, bbox) for each plate detected.
        """
        detections = self.detector.detect(frame)
        plates: List[Tuple[str, float, List[int]]] = []
        for class_name, conf, bbox in detections:
            if class_name.lower() in self.plate_class_names:
                plates.append((class_name, conf, bbox))
        return plates


class OcrEngine:
    """
    Wrapper around PaddleOCR for recognizing text from image crops.
    """

    def __init__(self) -> None:
        if PaddleOCR is None:
            raise RuntimeError(
                "paddleocr package is not installed; please install paddleocr to use ANPR"
            )
        # Initialize PaddleOCR; disable angle classifier for faster inference
        self.ocr = PaddleOCR(use_angle_cls=False, lang="en")

    def recognize(self, image: Any) -> Tuple[str, float]:
        """
        Recognize text from an image crop.

        Parameters
        ----------
        image: numpy.ndarray
            The cropped license plate image in BGR format.

        Returns
        -------
        Tuple[str, float]
            The recognized plate string and a confidence score between 0 and 1.
        """
        # Convert BGR to RGB for OCR
        if cv2 is None:
            raise RuntimeError("cv2 is not installed; cannot perform OCR")
        img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        # PaddleOCR expects image as ndarray
        results = self.ocr.ocr(img_rgb, cls=False)
        if not results:
            return "", 0.0
        # Flatten results and pick the line with highest confidence
        best_text = ""
        best_conf = 0.0
        for line in results:
            # Each line: list of (text region, (str, confidence))
            for (_, (text, conf)) in line:
                if conf is not None and conf > best_conf:
                    best_text = text
                    best_conf = conf
        return best_text, float(best_conf)


def normalize_plate_text(text: str) -> str:
    """
    Normalize a plate string by removing spaces and hyphens and converting
    to uppercase. Non-alphanumeric characters are stripped.

    Parameters
    ----------
    text: str
        The raw plate string from OCR.

    Returns
    -------
    str
        The normalized plate string.
    """
    # Remove whitespace and hyphens
    cleaned = text.replace(" ", "").replace("-", "")
    # Filter alphanumeric characters only
    filtered = "".join(ch for ch in cleaned if ch.isalnum())
    return filtered.upper()


class AnprProcessor:
    """
    Processor for ANPR logic. This class handles number plate recognition
    and rule evaluation for a single camera. It maintains an internal
    cache to avoid emitting duplicate events for the same plate within a
    configurable time window.
    """

    def __init__(
        self,
        camera_id: str,
        godown_id: str,
        rules: List[BaseRule],
        zone_polygons: Dict[str, List[Tuple[int, int]]],
        timezone: str,
        plate_detector: PlateDetector,
        ocr_engine: Optional[OcrEngine] = None,
        dedup_interval_sec: int = 30,
    ) -> None:
        self.logger = logging.getLogger(f"AnprProcessor-{camera_id}")
        self.camera_id = camera_id
        self.godown_id = godown_id
        self.rules_by_zone: Dict[str, List[BaseRule]] = {}
        for rule in rules:
            self.rules_by_zone.setdefault(rule.zone_id, []).append(rule)
        self.zone_polygons = zone_polygons
        try:
            self.tz = ZoneInfo(timezone)
        except Exception:
            self.tz = ZoneInfo("UTC")
        self.plate_detector = plate_detector
        # Instantiate OCR engine lazily if not provided
        if ocr_engine is None:
            try:
                self.ocr_engine = OcrEngine()
            except Exception as exc:
                self.logger.error("Failed to initialize OCR engine: %s", exc)
                self.ocr_engine = None  # type: ignore
        else:
            self.ocr_engine = ocr_engine
        self.dedup_interval_sec = dedup_interval_sec
        # Cache mapping (plate_text, zone_id) to last event time
        self.plate_cache: Dict[Tuple[str, str], datetime.datetime] = {}

    def _determine_zone(self, bbox: List[int]) -> Optional[str]:
        """Return the zone ID for a given bounding box center or None."""
        for zone_id, polygon in self.zone_polygons.items():
            if is_bbox_in_zone(bbox, polygon):
                return zone_id
        return None

    def _should_emit(self, plate_text: str, zone_id: str, now_utc: datetime.datetime) -> bool:
        """
        Determine whether an event should be emitted based on the last
        time this plate was seen in the same zone. Implements a simple
        time-based deduplication using ``dedup_interval_sec``.
        """
        key = (plate_text, zone_id)
        last_time = self.plate_cache.get(key)
        if last_time is None:
            return True
        if (now_utc - last_time).total_seconds() >= self.dedup_interval_sec:
            return True
        return False

    def _update_cache(self, plate_text: str, zone_id: str, now_utc: datetime.datetime) -> None:
        """
        Update the cache with the current time for the given plate and zone.
        """
        self.plate_cache[(plate_text, zone_id)] = now_utc

    def process_frame(
        self,
        frame: Any,
        now_utc: datetime.datetime,
        mqtt_client: MQTTClient,
    ) -> None:
        """
        Perform plate detection, OCR and rule evaluation on a single frame.

        Parameters
        ----------
        frame: numpy.ndarray
            The current frame in BGR format.
        now_utc: datetime.datetime
            Current UTC timestamp (naive or aware).
        mqtt_client: MQTTClient
            MQTT client used to publish events.
        """
        if frame is None:
            return
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=datetime.timezone.utc)
        now_local_dt = now_utc.astimezone(self.tz)
        timestamp_iso = now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        # Detect plates
        try:
            plates = self.plate_detector.detect_plates(frame)
        except Exception as exc:
            self.logger.error("Plate detection failed: %s", exc)
            return
        # Iterate over detected plates
        for (_, det_conf, bbox) in plates:
            # Determine zone
            zone_id = self._determine_zone(bbox)
            if zone_id is None:
                continue  # Only evaluate plates in defined zones
            # Crop plate region
            if cv2 is None:
                self.logger.error("cv2 is not installed; cannot crop plate for OCR")
                continue
            x1, y1, x2, y2 = bbox
            # Clip coordinates to frame bounds
            h, w = frame.shape[:2]
            x1 = max(0, min(x1, w - 1))
            y1 = max(0, min(y1, h - 1))
            x2 = max(0, min(x2, w - 1))
            y2 = max(0, min(y2, h - 1))
            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            # Run OCR
            plate_text_raw = ""
            ocr_conf = 0.0
            if self.ocr_engine is not None:
                try:
                    plate_text_raw, ocr_conf = self.ocr_engine.recognize(crop)
                except Exception as exc:
                    self.logger.error("OCR failed: %s", exc)
                    continue
            # Normalize plate text
            norm_plate = normalize_plate_text(plate_text_raw)
            if not norm_plate:
                continue
            # Combined confidence: multiply detection and OCR confidences
            combined_conf = float(det_conf) * float(ocr_conf)
            # Deduplicate events per plate per zone
            if not self._should_emit(norm_plate, zone_id, now_utc):
                continue
            # Evaluate rules to determine match status and event type
            rules = self.rules_by_zone.get(zone_id, [])
            match_status = "UNKNOWN"
            event_type = "ANPR_PLATE_DETECTED"
            severity = "info"
            rule_id = None
            # Determine plate status relative to blacklist/whitelist
            in_whitelist = False
            in_blacklist = False
            # Evaluate lists from rules
            for r in rules:
                if isinstance(r, AnprWhitelistRule):
                    # Normalise allowed list strings
                    allowed_norm = {normalize_plate_text(p) for p in r.allowed_plates}
                    if norm_plate in allowed_norm:
                        in_whitelist = True
                        rule_id = r.id
                    else:
                        # Plate not in whitelist; potential mismatch depending on rule
                        rule_id = r.id
                elif isinstance(r, AnprBlacklistRule):
                    blocked_norm = {normalize_plate_text(p) for p in r.blocked_plates}
                    if norm_plate in blocked_norm:
                        in_blacklist = True
                        rule_id = r.id
                elif isinstance(r, AnprMonitorRule):
                    if rule_id is None:
                        rule_id = r.id
                    # Monitor rule has no plate lists
                    pass
            # Determine match status and event type
            if in_blacklist:
                match_status = "BLACKLIST"
                event_type = "ANPR_PLATE_MISMATCH"
                severity = "warning"
            elif any(isinstance(r, AnprWhitelistRule) for r in rules):
                # Whitelist rule present
                if in_whitelist:
                    match_status = "WHITELIST"
                    event_type = "ANPR_PLATE_DETECTED"
                    severity = "info"
                else:
                    match_status = "UNKNOWN"
                    event_type = "ANPR_PLATE_MISMATCH"
                    severity = "warning"
            else:
                # No whitelist/blacklist rules; simple monitor
                match_status = "UNKNOWN"
                event_type = "ANPR_PLATE_DETECTED"
                severity = "info"
            # Build and publish event
            event = EventModel(
                godown_id=self.godown_id,
                camera_id=self.camera_id,
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                severity=severity,
                timestamp_utc=timestamp_iso,
                bbox=bbox,
                track_id=0,
                image_url=None,
                clip_url=None,
                meta=MetaModel(
                    zone_id=zone_id,
                    rule_id=rule_id or "",
                    confidence=combined_conf,
                    plate_text=norm_plate,
                    match_status=match_status,
                    extra={},
                ),
            )
            mqtt_client.publish_event(event)
            # Update cache
            self._update_cache(norm_plate, zone_id, now_utc)