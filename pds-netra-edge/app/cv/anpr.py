"""
ANPR (Automatic Number Plate Recognition) utilities for PDS Netra.

This module provides classes and functions to detect and recognize
vehicle number plates using a detection model and an OCR engine. It
also includes a processor that evaluates ANPR-specific rules and
emits events via MQTT.
"""

from __future__ import annotations

import csv
import datetime
import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
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
from ..events.mqtt_client import MQTTClient
from ..rules.loader import (
    AnprMonitorRule,
    AnprWhitelistRule,
    AnprBlacklistRule,
    BaseRule,
)

INDIA_PLATE_REGEX = re.compile(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$")


@dataclass
class RecognizedPlate:
    """Representation of a recognized number plate in a frame."""

    camera_id: str
    bbox: List[int]
    plate_text: str
    confidence: float
    timestamp_utc: str
    zone_id: Optional[str] = None
    det_conf: float = 0.0
    ocr_conf: float = 0.0
    match_status: str = "UNKNOWN"
    direction: Optional[str] = None


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

    def __init__(self, lang: Optional[List[str]] = None, use_gpu: bool = False) -> None:
        if PaddleOCR is None:
            raise RuntimeError(
                "paddleocr package is not installed; please install paddleocr to use ANPR"
            )
        if isinstance(lang, list) and lang:
            lang_value = str(lang[0])
        elif isinstance(lang, str) and lang:
            lang_value = lang
        else:
            lang_value = "en"
        # Initialize PaddleOCR; disable angle classifier for faster inference
        self.ocr = PaddleOCR(use_angle_cls=False, lang=lang_value, use_gpu=use_gpu)

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


def _is_valid_india_plate(plate: str) -> bool:
    return bool(INDIA_PLATE_REGEX.match(plate))


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
        ocr_lang: Optional[List[str]] = None,
        ocr_gpu: bool = False,
        ocr_every_n: int = 1,
        ocr_min_conf: float = 0.3,
        ocr_debug: bool = False,
        validate_india: bool = False,
        show_invalid: bool = False,
        registered_file: Optional[str] = None,
        save_csv: Optional[str] = None,
        save_crops_dir: Optional[str] = None,
        save_crops_max: Optional[int] = None,
        plate_rules_json: Optional[str] = None,
        gate_line: Optional[List[List[int]]] = None,
        inside_side: Optional[str] = None,
        direction_max_gap_sec: int = 120,
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
                self.ocr_engine = OcrEngine(lang=ocr_lang, use_gpu=ocr_gpu)
            except Exception as exc:
                self.logger.error("Failed to initialize OCR engine: %s", exc)
                self.ocr_engine = None  # type: ignore
        else:
            self.ocr_engine = ocr_engine
        self.dedup_interval_sec = int(dedup_interval_sec)
        self.ocr_every_n = max(1, int(ocr_every_n))
        self.ocr_min_conf = float(ocr_min_conf)
        self.ocr_debug = bool(ocr_debug)
        self.validate_india = bool(validate_india)
        self.show_invalid = bool(show_invalid)
        self.plate_rules_json = plate_rules_json

        self.save_csv = save_csv
        self._csv_ready = False
        self.save_crops_dir = Path(save_crops_dir).expanduser() if save_crops_dir else None
        self.save_crops_max = save_crops_max if save_crops_max is None else int(save_crops_max)
        self._saved_crops = 0
        self.registered_plates = self._load_registered_plates(registered_file)

        # Cache mapping (plate_text, zone_id) to last event time
        self.plate_cache: Dict[Tuple[str, str], datetime.datetime] = {}

        self.vote_window_sec = 20.0
        self.vote_history: Dict[str, List[Tuple[str, float, datetime.datetime]]] = {}

        self.frame_index = 0
        self.gate_line = self._parse_gate_line(gate_line)
        self.inside_side = (inside_side or "POSITIVE").strip().upper()
        self.direction_max_gap_sec = max(1, int(direction_max_gap_sec))
        self.plate_tracks: Dict[str, Tuple[int, datetime.datetime]] = {}

        # Crop tuning
        # shrink removes edges/background; pad adds a small border back
        self.crop_shrink_x = float(os.getenv("EDGE_ANPR_CROP_SHRINK_X", "0.04"))
        self.crop_shrink_y = float(os.getenv("EDGE_ANPR_CROP_SHRINK_Y", "0.12"))
        self.crop_pad_x = float(os.getenv("EDGE_ANPR_CROP_PAD_X", "0.06"))
        self.crop_pad_y = float(os.getenv("EDGE_ANPR_CROP_PAD_Y", "0.10"))

    def update_rules(self, rules: List[BaseRule]) -> None:
        """Replace rules for dynamic updates."""
        self.rules_by_zone = {}
        for rule in rules:
            self.rules_by_zone.setdefault(rule.zone_id, []).append(rule)

    def _determine_zone(self, bbox: List[int]) -> Optional[str]:
        """Return the zone ID for a given bounding box center or None."""
        if not self.zone_polygons:
            return "all"
        for zone_id, polygon in self.zone_polygons.items():
            if is_bbox_in_zone(bbox, polygon):
                return zone_id
        return None

    def _parse_gate_line(self, gate_line: Optional[List[List[int]]]) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
        if not gate_line or not isinstance(gate_line, list) or len(gate_line) != 2:
            return None
        try:
            p1 = gate_line[0]
            p2 = gate_line[1]
            if not (isinstance(p1, list) and isinstance(p2, list) and len(p1) == 2 and len(p2) == 2):
                return None
            return (float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1]))
        except Exception:
            return None

    def _line_side(self, p1: Tuple[float, float], p2: Tuple[float, float], p: Tuple[float, float]) -> int:
        (x1, y1), (x2, y2) = p1, p2
        px, py = p
        cross = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)
        if abs(cross) < 1e-6:
            return 0
        return 1 if cross > 0 else -1

    def _infer_direction(self, plate_norm: str, bbox: List[int], now_utc: datetime.datetime) -> str:
        if self.gate_line is None:
            return "UNKNOWN"
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        side = self._line_side(self.gate_line[0], self.gate_line[1], (cx, cy))
        if side == 0:
            return "UNKNOWN"
        last = self.plate_tracks.get(plate_norm)
        direction = "UNKNOWN"
        if last:
            last_side, last_seen = last
            if (now_utc - last_seen).total_seconds() <= self.direction_max_gap_sec and last_side != side:
                if (self.inside_side == "POSITIVE" and side > 0) or (self.inside_side == "NEGATIVE" and side < 0):
                    direction = "ENTRY"
                else:
                    direction = "EXIT"
        self.plate_tracks[plate_norm] = (side, now_utc)
        return direction

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

    def _vote_plate(
        self,
        zone_id: str,
        plate_text: str,
        combined_conf: float,
        now_utc: datetime.datetime,
    ) -> Tuple[str, float]:
        history = self.vote_history.get(zone_id, [])
        fresh_history: List[Tuple[str, float, datetime.datetime]] = []
        for p, c, ts in history:
            if (now_utc - ts).total_seconds() <= self.vote_window_sec:
                fresh_history.append((p, c, ts))
        fresh_history.append((plate_text, float(combined_conf), now_utc))
        self.vote_history[zone_id] = fresh_history

        scores: Dict[str, float] = {}
        max_conf: Dict[str, float] = {}
        for p, c, _ in fresh_history:
            scores[p] = scores.get(p, 0.0) + float(c)
            max_conf[p] = max(max_conf.get(p, 0.0), float(c))

        best_plate = plate_text
        best_score = scores.get(plate_text, 0.0)
        best_conf = max_conf.get(plate_text, combined_conf)

        for p in scores:
            s = scores[p]
            mc = max_conf.get(p, 0.0)
            if (s > best_score) or (abs(s - best_score) < 1e-6 and mc > best_conf) or (
                abs(s - best_score) < 1e-6 and abs(mc - best_conf) < 1e-6 and len(p) > len(best_plate)
            ):
                best_plate = p
                best_score = s
                best_conf = mc

        return best_plate, best_conf

    def _load_registered_plates(self, registered_file: Optional[str]) -> Optional[set[str]]:
        if not registered_file:
            return None
        try:
            path = Path(registered_file).expanduser()
            if not path.exists():
                self.logger.warning("Registered plates file not found: %s", path)
                return None
            data = path.read_text(encoding="utf-8").strip()
            if not data:
                return None
            if data.startswith("["):
                import json
                items = json.loads(data)
                if isinstance(items, list):
                    return {normalize_plate_text(str(x)) for x in items if x}
                if isinstance(items, dict):
                    values = items.get("plates") or items.get("registered") or []
                    if isinstance(values, list):
                        return {normalize_plate_text(str(x)) for x in values if x}
            # CSV/plain text
            plates = []
            for line in data.splitlines():
                line = line.strip()
                if line:
                    plates.append(normalize_plate_text(line))
            return set(plates)
        except Exception as exc:
            self.logger.warning("Failed to load registered plates: %s", exc)
            return None

    def _save_crop(self, crop: Any, plate_text: str, now_utc: datetime.datetime) -> None:
        if self.save_crops_dir is None:
            return
        if cv2 is None:
            return
        if self.save_crops_max is not None and self._saved_crops >= self.save_crops_max:
            return
        try:
            self.save_crops_dir.mkdir(parents=True, exist_ok=True)
            ts = now_utc.strftime("%Y%m%dT%H%M%S")
            safe_plate = re.sub(r"[^A-Za-z0-9]", "", plate_text) or "plate"
            filename = f"{safe_plate}_{ts}_{self._saved_crops}.jpg"
            out_path = self.save_crops_dir / filename
            cv2.imwrite(str(out_path), crop)
            self._saved_crops += 1
        except Exception:
            return

    def process_frame(
        self,
        frame: Any,
        now_utc: datetime.datetime,
        mqtt_client: MQTTClient,
        snapshotter=None,
    ) -> List[RecognizedPlate]:
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
        results_out: List[RecognizedPlate] = []
        if frame is None:
            return results_out
        self.frame_index += 1
        if self.ocr_every_n > 1 and (self.frame_index % self.ocr_every_n != 0):
            return results_out
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=datetime.timezone.utc)
        timestamp_iso = now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        # Detect plates
        try:
            plates = self.plate_detector.detect_plates(frame)
        except Exception as exc:
            self.logger.error("Plate detection failed: %s", exc)
            return results_out
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
            x1 = max(0, min(int(x1), w - 1))
            y1 = max(0, min(int(y1), h - 1))
            x2 = max(0, min(int(x2), w - 1))
            y2 = max(0, min(int(y2), h - 1))

            # Apply shrink/pad to improve OCR
            bw = max(1, x2 - x1)
            bh = max(1, y2 - y1)
            shrink_x = int(bw * self.crop_shrink_x)
            shrink_y = int(bh * self.crop_shrink_y)
            x1 = min(w - 1, max(0, x1 + shrink_x))
            y1 = min(h - 1, max(0, y1 + shrink_y))
            x2 = min(w - 1, max(0, x2 - shrink_x))
            y2 = min(h - 1, max(0, y2 - shrink_y))
            pad_x = int(bw * self.crop_pad_x)
            pad_y = int(bh * self.crop_pad_y)
            x1 = max(0, x1 - pad_x)
            y1 = max(0, y1 - pad_y)
            x2 = min(w - 1, x2 + pad_x)
            y2 = min(h - 1, y2 + pad_y)

            if x2 <= x1 or y2 <= y1:
                continue
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
            if self.ocr_debug:
                self.logger.info("OCR raw: %s (conf=%.3f)", plate_text_raw, float(ocr_conf))
            if float(ocr_conf) < self.ocr_min_conf:
                continue
            # Normalize plate text
            norm_plate = normalize_plate_text(plate_text_raw)
            if not norm_plate:
                continue
            plate_text_display = plate_text_raw.strip() or norm_plate
            # Combined confidence: multiply detection and OCR confidences
            combined_conf = float(det_conf) * float(ocr_conf)

            plate_text_display, voted_conf = self._vote_plate(zone_id, plate_text_display, combined_conf, now_utc)
            norm_plate = normalize_plate_text(plate_text_display)
            combined_conf = float(voted_conf)
            if not norm_plate:
                continue
            direction = self._infer_direction(norm_plate, bbox, now_utc)

            valid_plate = True
            if self.validate_india:
                valid_plate = _is_valid_india_plate(norm_plate)
                if not valid_plate and not self.show_invalid:
                    continue

            # Dedup
            if not self._should_emit(norm_plate, zone_id, now_utc):
                results_out.append(
                    RecognizedPlate(
                        camera_id=self.camera_id,
                        bbox=bbox,
                        plate_text=plate_text_display,
                        confidence=combined_conf,
                        timestamp_utc=timestamp_iso,
                        zone_id=zone_id,
                        det_conf=float(det_conf),
                        ocr_conf=float(ocr_conf),
                        match_status="DEDUP",
                        direction=direction,
                    )
                )
                continue

            registered = None
            if self.registered_plates is not None:
                registered = norm_plate in self.registered_plates

            extra: Dict[str, str] = {
                "det_conf": f"{float(det_conf):.4f}",
                "ocr_conf": f"{float(ocr_conf):.4f}",
            }
            if registered is not None:
                extra["registered"] = "true" if registered else "false"
            if not valid_plate:
                extra["valid_plate"] = "false"

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

            if not valid_plate and match_status != "BLACKLIST":
                match_status = "INVALID"
                event_type = "ANPR_PLATE_MISMATCH"
                severity = "warning"

            self._save_crop(crop, norm_plate, now_utc)
            self._append_csv_row(
                timestamp_iso,
                zone_id,
                norm_plate,
                det_conf,
                ocr_conf,
                combined_conf,
                valid_plate,
                "1" if registered else "0" if registered is not None else "",
                bbox=bbox,
                match_status=match_status,
            )

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
                    plate_text=plate_text_display,
                    plate_norm=norm_plate,
                    direction=direction,
                    match_status=match_status,
                    extra=extra,
                ),
            )
            mqtt_client.publish_event(event)
            self._update_cache(norm_plate, zone_id, now_utc)

            snapshot_url = None
            if snapshotter is not None:
                try:
                    snapshot_url = snapshotter(
                        frame,
                        f"anpr-{uuid.uuid4()}",
                        now_utc,
                        bbox=bbox,
                        label=f"ANPR {plate_text_display}",
                    )
                except Exception:
                    snapshot_url = None

            hit_event = EventModel(
                godown_id=self.godown_id,
                camera_id=self.camera_id,
                event_id=str(uuid.uuid4()),
                event_type="ANPR_HIT",
                severity="info",
                timestamp_utc=timestamp_iso,
                bbox=bbox,
                track_id=0,
                image_url=snapshot_url,
                clip_url=None,
                meta=MetaModel(
                    zone_id=zone_id if zone_id != "__GLOBAL__" else None,
                    rule_id=rule_id or "",
                    confidence=combined_conf,
                    plate_text=plate_text_display,
                    plate_norm=norm_plate,
                    direction=direction,
                    match_status=match_status,
                    extra=extra,
                ),
            )
            mqtt_client.publish_event(hit_event)

            results_out.append(
                RecognizedPlate(
                    camera_id=self.camera_id,
                    bbox=bbox,
                    plate_text=plate_text_display,
                    confidence=float(combined_conf),
                    timestamp_utc=timestamp_iso,
                    zone_id=zone_id,
                    det_conf=float(det_conf),
                    ocr_conf=float(ocr_conf),
                    match_status=match_status,
                    direction=direction,
                )
            )

            self.logger.info(
                "ANPR: plate=%s zone=%s det=%.3f ocr=%.3f conf=%.3f status=%s event=%s",
                plate_text_display,
                zone_id,
                float(det_conf),
                float(ocr_conf),
                float(combined_conf),
                match_status,
                event_type,
            )

        return results_out

    def _append_csv_row(self, ts, zone, text, det, ocr, comb, valid, reg, bbox=None, match_status: str = ""):
        if not self.save_csv:
            return
        try:
            try:
                parent = os.path.dirname(self.save_csv)
                if parent:
                    os.makedirs(parent, exist_ok=True)
            except Exception:
                pass

            with open(self.save_csv, "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                if (not self._csv_ready) and (f.tell() == 0):
                    writer.writerow(
                        [
                            "timestamp_utc",
                            "camera_id",
                            "zone_id",
                            "plate_text",
                            "det_conf",
                            "ocr_conf",
                            "combined_conf",
                            "valid",
                            "registered",
                            "match_status",
                            "bbox",
                        ]
                    )
                    self._csv_ready = True
                writer.writerow(
                    [
                        ts,
                        self.camera_id,
                        zone,
                        text,
                        f"{float(det):.4f}",
                        f"{float(ocr):.4f}",
                        f"{float(comb):.4f}",
                        "1" if valid else "0",
                        reg,
                        match_status,
                        "" if bbox is None else str(list(bbox)),
                    ]
                )
        except Exception as exc:
            self.logger.warning("ANPR CSV write failed (%s): %s", self.save_csv, exc)
