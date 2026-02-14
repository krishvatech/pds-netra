"""
ANPR (Automatic Number Plate Recognition) utilities for PDS Netra.

This module provides classes and functions to detect and recognize
vehicle number plates using a detection model and an OCR engine. It
also includes a processor that evaluates ANPR-specific rules and
emits events via MQTT.

MODIFIED:
1) ✅ Tight plate-only crop (geometry filter + crop shrink)
2) ✅ Slightly increase crop size (configurable pad)
3) ✅ JSON-based whitelist/blacklist verification
4) ✅ Save crops to OUTSIDE folder
5) ✅ Time Window Logic (Start/End time enforcement)

NEW FIXES (this patch):
A) ✅ ALWAYS run plate detection every frame (no early return)
B) ✅ OCR is throttled per-frame (ocr_every_n) but detection is continuous
C) ✅ OCR pipeline: light-preprocess first (fast) → strong-preprocess fallback (robust)
D) ✅ Minimum OCR acceptance strategy: run OCR with low min_conf, then apply your threshold
"""

from __future__ import annotations

import datetime
import os
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

# ---------------------------------------------------------------------
# Paddle runtime stabilization (Windows CPU)
# ---------------------------------------------------------------------
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["FLAGS_enable_pir_in_executor"] = "0"
os.environ["FLAGS_enable_new_ir"] = "0"
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

try:
    import cv2  # type: ignore
except ImportError:
    cv2 = None  # type: ignore

PaddleOCR = None  # type: ignore
paddle = None  # type: ignore

import numpy as np
from zoneinfo import ZoneInfo

from .yolo_detector import YoloDetector
from .zones import is_bbox_in_zone
from ..models.event import EventModel, MetaModel
from ..events.mqtt_client import MQTTClient
from ..rules.loader import BaseRule, AnprWhitelistRule, AnprBlacklistRule


# ---------------------------------------------------------------------
# Helper: Time Parsing
# ---------------------------------------------------------------------
def _parse_time(hhmm: str) -> datetime.time:
    """Parses 'HH:MM' string into a datetime.time object."""
    if not hhmm:
        return datetime.time(0, 0)
    try:
        parts = hhmm.split(":")
        return datetime.time(int(parts[0]), int(parts[1]))
    except Exception:
        return datetime.time(0, 0)

_INDIA_STATE_CODES = (
    "AN|AP|AR|AS|BR|CH|CG|DD|DL|DN|GA|GJ|HP|HR|JH|JK|KA|KL|LA|LD|"
    "MH|ML|MN|MP|MZ|NL|OD|PB|PY|RJ|SK|TN|TR|TS|UK|UP|WB"
)
_INDIA_STATE_CODE_SET = set(_INDIA_STATE_CODES.split("|"))
INDIA_PLATE_REGEX = re.compile(
    rf"^({_INDIA_STATE_CODES})\d{{2}}[A-Z]{{1,2}}\d{{4}}$|^\d{{2}}BH\d{{4}}[A-Z]{{2}}$"
)


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


class PlateDetector:
    """
    Wrapper around a YOLO detector for detecting license plates.
    """

    def __init__(self, detector: YoloDetector, plate_class_names: Optional[List[str]] = None) -> None:
        self.detector = detector
        if plate_class_names is None or len(plate_class_names) == 0:
            self.plate_class_names = None
        else:
            self.plate_class_names = {name.lower() for name in plate_class_names}

    @staticmethod
    def _is_plate_like_bbox(bbox: List[int], frame_shape) -> bool:
        try:
            h, w = frame_shape[:2]
            x1, y1, x2, y2 = bbox
            bw = max(1, int(x2) - int(x1))
            bh = max(1, int(y2) - int(y1))

            area_ratio = (bw * bh) / float(max(1, w * h))
            aspect = bw / float(bh)

            # Plates are small and wide.
            if area_ratio < 0.00015:   # too tiny -> noise
                return False
            if area_ratio > 0.05:      # too big -> truck body/board
                return False
            if aspect < 1.3 or aspect > 7.5:
                return False
            if (bh / float(max(1, h))) > 0.25:
                return False

            return True
        except Exception:
            return False

    def detect_plates(self, frame: Any) -> List[Tuple[str, float, List[int]]]:
        detections = self.detector.detect(frame)
        plates: List[Tuple[str, float, List[int]]] = []

        for class_name, conf, bbox in detections:
            if self.plate_class_names is not None and class_name.lower() not in self.plate_class_names:
                continue
            if not self._is_plate_like_bbox(bbox, frame.shape):
                continue
            plates.append((class_name, float(conf), bbox))

        plates.sort(key=lambda x: x[1], reverse=True)
        return plates


def _load_paddle():
    global paddle
    if paddle is None:
        try:
            import paddle as _paddle
        except ImportError:
            return None
        paddle = _paddle
    return paddle


def _load_paddleocr():
    global PaddleOCR
    if PaddleOCR is None:
        try:
            from paddleocr import PaddleOCR as _PaddleOCR
        except ImportError:
            return None
        PaddleOCR = _PaddleOCR
    return PaddleOCR


def _set_paddle_flags() -> None:
    pad = _load_paddle()
    if pad is None:
        return
    try:
        pad.set_flags({
            "FLAGS_use_mkldnn": 0,
            "FLAGS_enable_pir_api": 0,
            "FLAGS_enable_pir_in_executor": 0,
            "FLAGS_enable_new_ir": 0,
        })
    except Exception:
        pass


def _paddle_gpu_available() -> bool:
    pad = _load_paddle()
    if pad is None:
        return False
    try:
        return bool(pad.device.is_compiled_with_cuda())
    except Exception:
        return False


# ---------------------------------------------------------------------
# STRONG Preprocess for small/noisy plates
# ---------------------------------------------------------------------
def preprocess_plate_crop(bgr):
    """Strong preprocess (slower, but robust)."""
    if cv2 is None:
        return bgr

    try:
        bgr = cv2.copyMakeBorder(bgr, 8, 8, 16, 16, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    except Exception:
        pass

    h, _w = bgr.shape[:2]
    target_h = 360
    if h > 0 and h < target_h:
        scale = target_h / h
        try:
            bgr = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        except Exception:
            pass

    try:
        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        l, a, bb = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        l2 = clahe.apply(l)
        lab2 = cv2.merge((l2, a, bb))
        bgr = cv2.cvtColor(lab2, cv2.COLOR_LAB2BGR)
    except Exception:
        pass

    try:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        thr = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31, 5,
        )
        bgr = cv2.cvtColor(thr, cv2.COLOR_GRAY2BGR)
    except Exception:
        pass

    try:
        bgr = cv2.bilateralFilter(bgr, 7, 60, 60)
    except Exception:
        pass

    try:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        kernel = np.array([[0, -1, 0],
                           [-1, 5, -1],
                           [0, -1, 0]])
        sharp = cv2.filter2D(gray, -1, kernel)
        bgr = cv2.cvtColor(sharp, cv2.COLOR_GRAY2BGR)
    except Exception:
        pass

    return bgr


def preprocess_plate_crop_light(bgr):
    """Light preprocess (fast)."""
    if cv2 is None:
        return bgr

    try:
        bgr = cv2.copyMakeBorder(bgr, 6, 6, 12, 12, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    except Exception:
        pass

    h, _w = bgr.shape[:2]
    target_h = 360
    if h > 0 and h < target_h:
        scale = target_h / h
        try:
            bgr = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        except Exception:
            pass

    try:
        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        l, a, bb = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l2 = clahe.apply(l)
        lab2 = cv2.merge((l2, a, bb))
        bgr = cv2.cvtColor(lab2, cv2.COLOR_LAB2BGR)
    except Exception:
        pass

    return bgr


def _x_overlap_ratio(a: List[int], b: List[int]) -> float:
    ax1, _, ax2, _ = a
    bx1, _, bx2, _ = b
    inter = max(0, min(ax2, bx2) - max(ax1, bx1))
    min_w = max(1, min(ax2 - ax1, bx2 - bx1))
    return inter / float(min_w)


def _is_stacked_pair(a: List[int], b: List[int]) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    if ay1 > by1:
        ax1, ay1, ax2, ay2, bx1, by1, bx2, by2 = bx1, by1, bx2, by2, ax1, ay1, ax2, ay2
    h1, h2 = ay2 - ay1, by2 - by1
    if h1 <= 0 or h2 <= 0:
        return False
    gap = max(0, by1 - ay2)
    x_align = abs(((ax1 + ax2) / 2.0) - ((bx1 + bx2) / 2.0))
    max_w = max(ax2 - ax1, bx2 - bx1)
    return (
        _x_overlap_ratio([ax1, ay1, ax2, ay2], [bx1, by1, bx2, by2]) >= 0.45
        and gap <= 0.6 * max(h1, h2)
        and x_align <= 0.6 * max_w
    )


def _merge_stacked_plates(plates: List[Tuple[str, float, List[int]]]) -> List[Tuple[str, float, List[int]]]:
    if len(plates) < 2:
        return plates
    merged: List[Tuple[str, float, List[int]]] = []
    used = set()
    for i, (cls1, conf1, box1) in enumerate(plates):
        if i in used:
            continue
        best_j = None
        best_box = None
        best_conf = conf1
        for j in range(i + 1, len(plates)):
            if j in used:
                continue
            cls2, conf2, box2 = plates[j]
            if _is_stacked_pair(box1, box2):
                x1 = min(box1[0], box2[0])
                y1 = min(box1[1], box2[1])
                x2 = max(box1[2], box2[2])
                y2 = max(box1[3], box2[3])
                best_j = j
                best_box = [x1, y1, x2, y2]
                best_conf = max(conf1, conf2)
                break
        if best_j is not None and best_box is not None:
            used.add(i)
            used.add(best_j)
            merged.append((cls1, best_conf, best_box))
        else:
            merged.append((cls1, conf1, box1))
    return merged


def _init_paddle_ocr(paddleocr_cls, lang: str, use_gpu: bool):
    configs = [
        # Prefer disabling doc orientation/unwarping/textline orientation on Jetson
        # because these internal pipelines can trigger native crashes in some
        # Paddle/PaddleOCR builds.
        {
            "lang": lang,
            "use_gpu": use_gpu,
            "use_angle_cls": True,
            "enable_mkldnn": False,
            "show_log": False,
            "det_db_thresh": 0.10,
            "det_db_box_thresh": 0.30,
            "det_db_unclip_ratio": 2.0,
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
        },
        {
            "lang": lang,
            "use_angle_cls": True,
            "enable_mkldnn": False,
            "show_log": False,
            "det_db_thresh": 0.10,
            "det_db_box_thresh": 0.30,
            "det_db_unclip_ratio": 2.0,
        },
        {
            "lang": lang,
            "use_angle_cls": True,
            "enable_mkldnn": False,
            "det_db_thresh": 0.10,
            "det_db_box_thresh": 0.30,
            "det_db_unclip_ratio": 2.0,
        },
        {"lang": lang, "use_angle_cls": True},
    ]

    logger = logging.getLogger("OcrEngine")
    last_exc = None
    for i, params in enumerate(configs):
        if use_gpu and "use_gpu" not in params:
            params["use_gpu"] = use_gpu
        try:
            return paddleocr_cls(**params)
        except Exception as e:
            last_exc = e
            logger.debug("PaddleOCR init failed config %s: %s", i, e)

    logger.error("All PaddleOCR configurations failed: %s", last_exc)
    return None


def normalize_plate_text(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", text or "")
    return cleaned.upper()


def is_valid_india_plate(text: str) -> bool:
    if not text:
        return False
    t = normalize_plate_text(text)
    return bool(INDIA_PLATE_REGEX.match(t))


def format_indian_plate(text: str) -> str:
    cleaned = normalize_plate_text(text)
    if not cleaned:
        return ""
    m = re.match(r"^([A-Z]{2})(\d{2})([A-Z]{1,2})(\d{4})$", cleaned)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}"
    m = re.match(r"^(\d{2})(BH)(\d{4})([A-Z]{2})$", cleaned)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}"
    return cleaned


def _maybe_swap_stacked_plate(text: str) -> Optional[str]:
    t = normalize_plate_text(text)
    if not t:
        return None
    patterns = [
        r"^([A-Z]{1,2}\d{4})([A-Z]{2}\d{2})$",
        r"^(\d{4}[A-Z]{1,2})([A-Z]{2}\d{2})$",
    ]
    for pat in patterns:
        m = re.match(pat, t)
        if m:
            return f"{m.group(2)}{m.group(1)}"
    return None


def _expand_series_letters(text: str) -> List[str]:
    t = normalize_plate_text(text)
    if not t:
        return []
    m = re.match(r"^([A-Z]{2}\d{2})([A-Z0-9]{1,2})(\d{4})$", t)
    if not m:
        return []

    prefix, series, suffix = m.groups()
    if series.isalpha():
        return []

    digit_map = {
        "0": ["O", "D"],
        "1": ["I"],
        "2": ["Z"],
        "5": ["S", "D"],
        "6": ["G"],
        "8": ["B"],
        "9": ["G"],
    }

    choices: List[List[str]] = []
    for ch in series:
        if ch.isalpha():
            choices.append([ch])
        else:
            choices.append(digit_map.get(ch, []))

    if not all(choices):
        return []

    results: List[str] = []

    def _build(idx: int, acc: List[str]) -> None:
        if len(results) >= 20:
            return
        if idx >= len(choices):
            results.append(f"{prefix}{''.join(acc)}{suffix}")
            return
        for opt in choices[idx]:
            acc.append(opt)
            _build(idx + 1, acc)
            acc.pop()

    _build(0, [])
    return results


def cleanup_plate_candidates(raw: str) -> List[str]:
    base = normalize_plate_text(raw)
    if not base:
        return []
    subs = {"O": "0", "I": "1", "Z": "2", "S": "5", "B": "8", "Q": "0"}
    cands = [base]
    fixed = "".join(subs.get(ch, ch) for ch in base)
    if fixed != base:
        cands.append(fixed)

    rev = {"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B"}
    fixed2 = "".join(rev.get(ch, ch) for ch in base)
    if fixed2 != base:
        cands.append(fixed2)

    swapped = []
    for cand in cands:
        alt = _maybe_swap_stacked_plate(cand)
        if alt:
            swapped.append(alt)

    expanded = []
    for cand in cands + swapped:
        expanded.extend(_expand_series_letters(cand))

    return list(set(cands + swapped + expanded))


def _coerce_char_to_letter(ch: str) -> Tuple[Optional[str], int]:
    if ch.isalpha():
        return ch.upper(), 0
    digit_to_letter = {
        "0": "O",
        "1": "I",
        "2": "Z",
        "4": "A",
        "5": "S",
        "6": "G",
        "7": "T",
        "8": "B",
        "9": "G",
    }
    if ch in digit_to_letter:
        return digit_to_letter[ch], 1
    return None, 0


def _coerce_char_to_digit(ch: str) -> Tuple[Optional[str], int]:
    if ch.isdigit():
        return ch, 0
    letter_to_digit = {
        "O": "0",
        "Q": "0",
        "D": "0",
        "I": "1",
        "L": "1",
        "Z": "2",
        "S": "5",
        "A": "4",
        "T": "7",
        "G": "6",
        "B": "8",
    }
    ch = ch.upper()
    if ch in letter_to_digit:
        return letter_to_digit[ch], 1
    return None, 0


def _coerce_to_pattern(text: str, pattern: str) -> Tuple[Optional[str], int]:
    if len(text) != len(pattern):
        return None, 0
    out = []
    cost = 0
    for ch, need in zip(text, pattern):
        if need == "L":
            val, c = _coerce_char_to_letter(ch)
            if val is None:
                return None, 0
            out.append(val)
            cost += c
        elif need == "D":
            val, c = _coerce_char_to_digit(ch)
            if val is None:
                return None, 0
            out.append(val)
            cost += c
        else:
            if ch.upper() == need:
                out.append(need)
            else:
                val, c = _coerce_char_to_letter(ch)
                if val != need:
                    return None, 0
                out.append(need)
                cost += c
    return "".join(out), cost


def guess_india_plate(text: str, min_len: int = 8, max_cost: int = 2) -> Optional[str]:
    base = normalize_plate_text(text)
    if not base:
        return None
    if len(base) < int(min_len):
        return None
    if not (
        (len(base) >= 2 and base[0].isalpha() and base[1].isalpha())
        or (len(base) >= 4 and base[2:4] == "BH")
    ):
        return None
    if len(base) >= 2 and base[0:2].isalpha() and base[0:2] not in _INDIA_STATE_CODE_SET:
        return None
    if is_valid_india_plate(base):
        return format_indian_plate(base)

    patterns = []
    for s in (1, 2):
        patterns.append("LL" + ("D" * 2) + ("L" * s) + "DDDD")
    patterns.append("DD" + "BH" + "DDDD" + ("L" * 2))

    best = None
    best_cost = None
    for pat in patterns:
        plen = len(pat)
        if len(base) < plen:
            continue
        for i in range(0, len(base) - plen + 1):
            sub = base[i:i + plen]
            cand, cost = _coerce_to_pattern(sub, pat)
            if cand is None:
                continue
            if not is_valid_india_plate(cand):
                continue
            if cost > int(max_cost):
                continue
            if best_cost is None or cost < best_cost:
                best_cost = cost
                best = cand
                if best_cost == 0:
                    break
        if best_cost == 0:
            break

    if best is None:
        return None
    return format_indian_plate(best)


def load_registered_plates(path: Optional[str]) -> set[str]:
    plates: set[str] = set()
    if not path or not os.path.exists(path):
        return plates
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if raw and not raw.startswith("#"):
                plates.add(normalize_plate_text(raw))
    return plates


# ---------------- JSON RULES (VERIFIED / ALERT) ----------------
def load_plate_rules_json(path: Optional[str]) -> Tuple[set[str], set[str]]:
    """
    JSON format:
      { "whitelist": ["WB23D5690"], "blacklist": ["DL01ZZ9999"] }
    """
    wl: set[str] = set()
    bl: set[str] = set()
    if not path:
        return wl, bl
    try:
        if not os.path.exists(path):
            return wl, bl
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        wl = {normalize_plate_text(x) for x in (data.get("whitelist") or []) if str(x).strip()}
        bl = {normalize_plate_text(x) for x in (data.get("blacklist") or []) if str(x).strip()}
    except Exception:
        return set(), set()
    return wl, bl


def decide_plate_status(norm_plate: str, whitelist: set[str], blacklist: set[str]) -> Tuple[str, str, str]:
    """
    Returns: (match_status, event_type, severity)
    """
    if norm_plate in blacklist:
        return ("BLACKLIST", "ANPR_PLATE_ALERT", "critical")

    if whitelist:
        if norm_plate in whitelist:
            return ("VERIFIED", "ANPR_PLATE_VERIFIED", "info")
        return ("NOT_VERIFIED", "ANPR_PLATE_ALERT", "warning")

    return ("DETECTED", "ANPR_PLATE_DETECTED", "info")
# ----------------------------------------------------------------


def _parse_paddle_ocr_detrec(ocr_results) -> Tuple[str, float]:
    if not ocr_results:
        return "", 0.0
    texts: List[str] = []
    confs: List[float] = []
    for block in ocr_results:
        if not block:
            continue
        for line in block:
            if not line or len(line) < 2:
                continue
            payload = line[1]
            if isinstance(payload, (list, tuple)) and len(payload) >= 2:
                t, c = payload[0], payload[1]
                t = normalize_plate_text(str(t))
                try:
                    c = float(c)
                except Exception:
                    c = 0.0
                if len(t) > 1:
                    texts.append(t)
                    confs.append(c)
    if not texts:
        return "", 0.0
    return "".join(texts), (sum(confs) / len(confs)) if confs else 0.0


def _parse_paddle_ocr_reconly(res) -> Tuple[str, float]:
    if not res:
        return "", 0.0

    if len(res) == 1 and isinstance(res[0], list):
        maybe = res[0]
        if maybe and isinstance(maybe[0], (list, tuple)):
            res = maybe

    best_t, best_c = "", 0.0
    for item in res:
        t, c = "", 0.0
        if isinstance(item, list) and len(item) == 1 and isinstance(item[0], (list, tuple)) and len(item[0]) >= 2:
            t, c = item[0][0], item[0][1]
        elif isinstance(item, (list, tuple)) and len(item) >= 2 and isinstance(item[0], (str, int, float)):
            t, c = item[0], item[1]
        elif isinstance(item, tuple) and len(item) >= 2:
            t, c = item[0], item[1]

        t = normalize_plate_text(str(t))
        try:
            c = float(c)
        except Exception:
            c = 0.0
        if not t:
            continue

        if (c > best_c) or (abs(c - best_c) < 1e-6 and len(t) > len(best_t)):
            best_t, best_c = t, c

    return best_t, best_c


def _parse_paddle_ocr_predict(res) -> Tuple[str, float]:
    if not res:
        return "", 0.0

    texts: List[str] = []
    confs: List[float] = []
    for item in res:
        if not item or not hasattr(item, "get"):
            continue
        rec_texts = item.get("rec_texts", [])
        rec_scores = item.get("rec_scores", [])

        for i, t in enumerate(rec_texts):
            t = normalize_plate_text(str(t))
            if not t:
                continue
            texts.append(t)
            try:
                confs.append(float(rec_scores[i]))
            except Exception:
                confs.append(0.0)

    if not texts:
        return "", 0.0
    return "".join(texts), (sum(confs) / len(confs)) if confs else 0.0



class OcrEngine:
    """
    OCR tuned for Indian plates.

    Notes:
    - Plate crops are already localized, so rec-only often works better.
    - We still fallback to det+rec for safety.
    - We keep the internal `min_conf` low and apply the real threshold in AnprProcessor.
    - Set EDGE_ANPR_OCR_DUMP=true to log raw PaddleOCR outputs (debug).
    """

    def __init__(self, languages: List[str], gpu: bool) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        paddleocr_cls = _load_paddleocr()
        if paddleocr_cls is None:
            raise RuntimeError(
                "paddleocr package is not installed. "
                "Install paddleocr/paddlepaddle in the edge image (Jetson: use docker/Dockerfile.jp6) "
                "or set EDGE_ANPR_DISABLE_OCR=true to run detection-only ANPR."
            )

        _set_paddle_flags()
        use_gpu = bool(gpu) and _paddle_gpu_available()
        lang = languages[0] if languages else "en"

        self.ocr = _init_paddle_ocr(paddleocr_cls, lang=lang, use_gpu=use_gpu)
        if self.ocr is None:
            raise RuntimeError("Failed to initialize PaddleOCR.")

    def recognize(self, image_bgr: Any, min_conf: float = 0.05) -> Tuple[str, float]:
        if cv2 is None or image_bgr is None:
            return "", 0.0

        # Ensure uint8 + contiguous
        try:
            if getattr(image_bgr, "dtype", None) != np.uint8:
                image_bgr = np.clip(image_bgr, 0, 255).astype(np.uint8)
            image_bgr = np.ascontiguousarray(image_bgr)
        except Exception:
            pass

        # Upscale small crops (helps a lot for CCTV plates)
        try:
            h, _w = image_bgr.shape[:2]
            scale = 1.0
            if h < 90:
                scale = 3.0
            elif h < 160:
                scale = 2.5
            elif h < 260:
                scale = 2.0
            elif h < 340:
                scale = 1.6
            if scale > 1.0:
                image_bgr = cv2.resize(image_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        except Exception:
            pass

        # Paddle expects RGB
        try:
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        except Exception:
            image_rgb = image_bgr

        dump_raw = os.getenv("EDGE_ANPR_OCR_DUMP", "false").lower() in {"1", "true", "yes", "y"}

        # Helper: choose best combined string & mean conf
        def _best(texts: List[str], confs: List[float]) -> Tuple[str, float]:
            if not texts:
                return "", 0.0
            text = "".join(texts)
            conf = (sum(confs) / len(confs)) if confs else 0.0
            return text, float(conf)

        # 1) Newer API: predict()
        if hasattr(self.ocr, "predict"):
            try:
                res = self.ocr.predict(image_rgb)
                if dump_raw:
                    self.logger.info("ANPR OCR raw predict: %s", str(res)[:800])
                text, conf = _parse_paddle_ocr_predict(res)
                if text and conf >= float(min_conf):
                    return text, float(conf)
            except Exception as exc:
                self.logger.debug("PaddleOCR predict failed: %s", exc)

        # 2) Classic API: ocr(det=False) rec-only first
        try:
            res = self.ocr.ocr(image_rgb, det=False, rec=True, cls=True)
            if dump_raw:
                self.logger.info("ANPR OCR raw rec-only: %s", str(res)[:800])
            text, conf = _parse_paddle_ocr_reconly(res)
            if text and conf >= float(min_conf):
                return text, float(conf)
        except Exception as exc:
            self.logger.debug("PaddleOCR rec-only failed: %s", exc)

        # 3) Fallback: det+rec
        try:
            res2 = self.ocr.ocr(image_rgb, det=True, cls=True)
            if dump_raw:
                self.logger.info("ANPR OCR raw det+rec: %s", str(res2)[:800])
            text2, conf2 = _parse_paddle_ocr_detrec(res2)
            if text2 and conf2 >= float(min_conf):
                return text2, float(conf2)
        except Exception as exc:
            self.logger.debug("PaddleOCR det+rec failed: %s", exc)

        return "", 0.0
class AnprProcessor:
    def __init__(
        self,
        camera_id: str,
        godown_id: str,
        rules: List[BaseRule],
        zone_polygons: Dict[str, List[Tuple[int, int]]],
        timezone: str,
        plate_detector: PlateDetector,
        ocr_engine: Optional[OcrEngine] = None,
        ocr_lang: Optional[List[str]] = None,
        ocr_gpu: Optional[bool] = None,
        ocr_every_n: int = 1,
        ocr_min_conf: float = 0.3,
        ocr_debug: bool = False,
        validate_india: bool = False,
        show_invalid: bool = False,
        registered_file: Optional[str] = None,
        save_crops_dir: Optional[str] = None,
        save_crops_max: Optional[int] = None,
        dedup_interval_sec: int = 30,
        plate_rules_json: Optional[str] = None,
        allowed_start: str = "00:00",
        allowed_end: str = "23:59",
        gate_line: Optional[List[List[int]]] = None,
        inside_side: Optional[str] = None,
        direction_max_gap_sec: int = 120,
    ) -> None:
        self.logger = logging.getLogger(f"AnprProcessor-{camera_id}")
        self.camera_id = camera_id
        self.godown_id = godown_id

        self.require_zone = os.getenv("EDGE_ANPR_REQUIRE_ZONE", "false").lower() in {"1", "true", "yes"}

        self.rules_by_zone: Dict[str, List[BaseRule]] = {}

        self.zone_polygons = zone_polygons
        try:
            self.tz = ZoneInfo(timezone)
        except Exception:
            self.tz = ZoneInfo("UTC")

        self.allowed_start = _parse_time(allowed_start)
        self.allowed_end = _parse_time(allowed_end)

        self.gate_line = self._parse_gate_line(gate_line)
        inside_side_norm = str(inside_side).strip().upper() if inside_side else None
        if inside_side_norm not in {"POSITIVE", "NEGATIVE"}:
            inside_side_norm = "POSITIVE" if self.gate_line else None
        self.inside_side = inside_side_norm
        self.direction_max_gap_sec = max(1, int(direction_max_gap_sec))
        self.plate_tracks: Dict[str, Tuple[int, datetime.datetime]] = {}

        self.plate_detector = plate_detector

        ocr_disabled = os.getenv("EDGE_ANPR_DISABLE_OCR", "false").strip().lower() in {"1", "true", "yes", "y"}
        if ocr_disabled:
            self.ocr_engine = None
            self.logger.warning("ANPR OCR disabled via EDGE_ANPR_DISABLE_OCR; plate OCR will be skipped.")
        elif ocr_engine is None:
            try:
                self.ocr_engine = OcrEngine(ocr_lang or ["en"], ocr_gpu or False)
                self.logger.info("ANPR OCR engine initialized (PaddleOCR)")
            except Exception as exc:
                self.logger.error("Failed to initialize OCR engine: %s", exc)
                self.ocr_engine = None
        else:
            self.ocr_engine = ocr_engine

        self.ocr_every_n = max(int(ocr_every_n), 1)
        self.ocr_min_conf = float(ocr_min_conf)
        self.ocr_debug = bool(ocr_debug)
        self.guess_promote_conf = float(os.getenv("EDGE_ANPR_GUESS_PROMOTE_CONF", "0.85"))
        self.guess_promote_min_votes = int(os.getenv("EDGE_ANPR_GUESS_PROMOTE_MIN_VOTES", "3"))

        self.validate_india = bool(validate_india)
        self.show_invalid = bool(show_invalid)

        self.registered_plates = load_registered_plates(registered_file)

        self.plate_rules_json = ""
        self.whitelist_plates: set[str] = set()
        self.blacklist_plates: set[str] = set()
        self.update_rules(rules)

        use_json_rules = os.getenv("EDGE_ANPR_USE_JSON_RULES", "false").lower() in {"1", "true", "yes"}
        if use_json_rules and not (self.whitelist_plates or self.blacklist_plates):
            self.plate_rules_json = plate_rules_json or os.getenv("EDGE_ANPR_RULES_JSON", "")
            self.whitelist_plates, self.blacklist_plates = load_plate_rules_json(self.plate_rules_json)
            if self.whitelist_plates or self.blacklist_plates:
                self.logger.info(
                    "ANPR JSON rules loaded (fallback): whitelist=%d blacklist=%d path=%s window=%s-%s",
                    len(self.whitelist_plates),
                    len(self.blacklist_plates),
                    self.plate_rules_json,
                    self.allowed_start,
                    self.allowed_end,
                )

        self.save_crops_dir = os.getenv("EDGE_ANPR_CROPS_DIR", "") or save_crops_dir
        if self.save_crops_dir:
            os.makedirs(self.save_crops_dir, exist_ok=True)

        self.save_crops_max = save_crops_max
        self._crop_save_count = 0


        self.dedup_interval_sec = int(dedup_interval_sec)
        self.plate_cache: Dict[Tuple[str, str], datetime.datetime] = {}

        self.vote_window_sec = 20.0
        self.vote_history: Dict[str, List[Tuple[str, float, datetime.datetime]]] = {}

        self.frame_index = 0

        # Crop tuning
        self.crop_shrink_x = float(os.getenv("EDGE_ANPR_CROP_SHRINK_X", "0.04"))
        self.crop_shrink_y = float(os.getenv("EDGE_ANPR_CROP_SHRINK_Y", "0.12"))
        self.crop_pad_x = float(os.getenv("EDGE_ANPR_CROP_PAD_X", "0.06"))
        self.crop_pad_y = float(os.getenv("EDGE_ANPR_CROP_PAD_Y", "0.10"))

    def _guess_can_promote(self, zone_id: str, norm_plate: str, conf: float, now_utc: datetime.datetime) -> bool:
        if conf < self.guess_promote_conf:
            return False
        history = self.vote_history.get(zone_id, [])
        if not history:
            return False
        cutoff = now_utc - datetime.timedelta(seconds=self.vote_window_sec)
        count = 0
        for p, _, ts in history:
            if ts < cutoff:
                continue
            if normalize_plate_text(p) == norm_plate:
                count += 1
        return count >= self.guess_promote_min_votes

    def _plates_from_rules(self, rules: List[BaseRule]) -> tuple[set[str], set[str]]:
        whitelist: set[str] = set()
        blacklist: set[str] = set()
        for rule in rules or []:
            rtype = str(getattr(rule, "type", "") or "").strip().upper()
            if isinstance(rule, AnprWhitelistRule) or rtype == "ANPR_WHITELIST_ONLY":
                for plate in (getattr(rule, "allowed_plates", None) or []):
                    norm = normalize_plate_text(str(plate))
                    if norm:
                        whitelist.add(norm)
            if isinstance(rule, AnprBlacklistRule) or rtype == "ANPR_BLACKLIST_ALERT":
                for plate in (getattr(rule, "blocked_plates", None) or []):
                    norm = normalize_plate_text(str(plate))
                    if norm:
                        blacklist.add(norm)
        return whitelist, blacklist

    def update_rules(self, rules: List[BaseRule]) -> None:
        self.rules_by_zone = {}
        for rule in rules or []:
            zid = getattr(rule, "zone_id", None) or "__GLOBAL__"
            self.rules_by_zone.setdefault(zid, []).append(rule)
        self.whitelist_plates, self.blacklist_plates = self._plates_from_rules(rules)
        if self.whitelist_plates or self.blacklist_plates:
            self.logger.info(
                "ANPR DB rules loaded: whitelist=%d blacklist=%d window=%s-%s",
                len(self.whitelist_plates),
                len(self.blacklist_plates),
                self.allowed_start,
                self.allowed_end,
            )

    def _determine_zone(self, bbox: List[int]) -> Optional[str]:
        if not self.zone_polygons:
            return "__GLOBAL__"
        for zone_id, polygon in self.zone_polygons.items():
            try:
                if is_bbox_in_zone(bbox, polygon):
                    return zone_id
            except Exception:
                continue
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
        key = (plate_text, zone_id)
        last_time = self.plate_cache.get(key)
        if last_time is None:
            return True
        return (now_utc - last_time).total_seconds() >= self.dedup_interval_sec

    def _update_cache(self, plate_text: str, zone_id: str, now_utc: datetime.datetime) -> None:
        self.plate_cache[(plate_text, zone_id)] = now_utc

    def _vote_plate(
        self,
        zone_id: str,
        plate_text: str,
        combined_conf: float,
        now_utc: datetime.datetime,
    ) -> Tuple[str, float]:
        history = self.vote_history.setdefault(zone_id, [])
        history.append((plate_text, combined_conf, now_utc))
        cutoff = now_utc - datetime.timedelta(seconds=self.vote_window_sec)
        history[:] = [h for h in history if h[2] >= cutoff]

        scores: Dict[str, float] = {}
        max_conf: Dict[str, float] = {}
        for p, c, _ in history:
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

    def _inside_time_window(self, now_t: datetime.time) -> bool:
        if self.allowed_start <= self.allowed_end:
            return self.allowed_start <= now_t <= self.allowed_end
        return now_t >= self.allowed_start or now_t <= self.allowed_end

    def process_frame(
        self,
        frame: Any,
        now_utc: datetime.datetime,
        mqtt_client: MQTTClient,
        snapshotter=None,
    ) -> List[RecognizedPlate]:
        results_out: List[RecognizedPlate] = []
        if frame is None:
            return results_out

        self.frame_index += 1

        # IMPORTANT FIX:
        # - Do NOT return early here.
        # - Always detect plates every frame.
        do_ocr_this_frame = (self.frame_index % self.ocr_every_n == 0)

        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=datetime.timezone.utc)
        timestamp_iso = now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")

        local_now = now_utc.astimezone(self.tz)
        inside_time = self._inside_time_window(local_now.time())

        try:
            plates = self.plate_detector.detect_plates(frame)
        except Exception as exc:
            self.logger.debug("ANPR detect_plates failed: %s", exc)
            return results_out

        if not plates:
            if self.ocr_debug:
                self.logger.info("ANPR: no plate detections (frame=%d)", self.frame_index)
            return results_out

        plates = _merge_stacked_plates(plates)

        for (_, det_conf, bbox) in plates:
            zone_id = self._determine_zone(bbox)

            if zone_id is None and self.require_zone:
                continue
            if zone_id is None:
                zone_id = "__GLOBAL__"

            if cv2 is None:
                continue

            # ---- CROP (tight + slight pad) ----
            try:
                x1, y1, x2, y2 = bbox
                h, w = frame.shape[:2]

                box_w = max(1, x2 - x1)
                box_h = max(1, y2 - y1)

                dx = int(box_w * self.crop_shrink_x)
                dy = int(box_h * self.crop_shrink_y)

                x1s = x1 + dx
                y1s = y1 + dy
                x2s = x2 - dx
                y2s = y2 - dy

                px = int(box_w * self.crop_pad_x)
                py = int(box_h * self.crop_pad_y)

                x1c = max(0, x1s - px)
                y1c = max(0, y1s - py)
                x2c = min(w, x2s + px)
                y2c = min(h, y2s + py)

                if x2c <= x1c or y2c <= y1c:
                    continue

                crop = frame[y1c:y2c, x1c:x2c]
                if crop.size == 0:
                    continue
            except Exception:
                continue

            # Save crops (debug)
            if self.save_crops_dir:
                if self.save_crops_max is None or self._crop_save_count < self.save_crops_max:
                    try:
                        f_name = os.path.join(
                            self.save_crops_dir,
                            f"crop_{self.frame_index}_{float(det_conf):.2f}_{uuid.uuid4().hex[:4]}.jpg",
                        )
                        crop_out = crop
                        try:
                            crop_out = cv2.resize(crop, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
                        except Exception:
                            pass
                        cv2.imwrite(f_name, crop_out)
                        self._crop_save_count += 1
                    except Exception:
                        pass

            # If OCR is throttled off this frame, just skip OCR but keep loop alive
            if not do_ocr_this_frame:
                if self.ocr_debug:
                    self.logger.info("ANPR: OCR skipped (frame=%d) det=%.3f zone=%s", self.frame_index, det_conf, zone_id)
                results_out.append(
                    RecognizedPlate(
                        camera_id=self.camera_id,
                        bbox=bbox,
                        plate_text="",
                        confidence=float(det_conf),
                        timestamp_utc=timestamp_iso,
                        zone_id=zone_id,
                        det_conf=float(det_conf),
                        ocr_conf=0.0,
                        match_status="NO_OCR",
                    )
                )
                continue

            plate_text_raw, ocr_conf = "", 0.0
            if self.ocr_engine:
                try:
                    # FAST PATH FIRST
                    crop_light = preprocess_plate_crop_light(crop)
                    plate_text_raw, ocr_conf = self.ocr_engine.recognize(crop_light, min_conf=0.05)

                    # If weak/empty, use STRONG preprocessing
                    if not plate_text_raw or float(ocr_conf) < 0.10:
                        crop_strong = preprocess_plate_crop(crop)
                        plate_text_raw, ocr_conf = self.ocr_engine.recognize(crop_strong, min_conf=0.05)

                except Exception as exc:
                    self.logger.debug("ANPR OCR failed: %s", exc)
                    continue

            # Enforce your threshold here (not inside PaddleOCR)
            if not plate_text_raw or float(ocr_conf) < float(self.ocr_min_conf):
                if self.ocr_debug:
                    self.logger.info(
                        "ANPR: OCR low/empty (frame=%d) det=%.3f ocr=%.3f raw=%s",
                        self.frame_index, det_conf, ocr_conf, plate_text_raw
                    )
                results_out.append(
                    RecognizedPlate(
                        camera_id=self.camera_id,
                        bbox=bbox,
                        plate_text="",
                        confidence=float(det_conf),
                        timestamp_utc=timestamp_iso,
                        zone_id=zone_id,
                        det_conf=float(det_conf),
                        ocr_conf=float(ocr_conf),
                        match_status="NO_OCR",
                    )
                )
                continue

            candidates = cleanup_plate_candidates(plate_text_raw)
            if not candidates:
                results_out.append(
                    RecognizedPlate(
                        camera_id=self.camera_id,
                        bbox=bbox,
                        plate_text="",
                        confidence=float(det_conf),
                        timestamp_utc=timestamp_iso,
                        zone_id=zone_id,
                        det_conf=float(det_conf),
                        ocr_conf=float(ocr_conf),
                        match_status="NO_OCR",
                    )
                )
                continue

            plate_text_display = ""
            guessed_plate = False

            for cand in candidates:
                cand_norm = normalize_plate_text(cand)
                if is_valid_india_plate(cand_norm):
                    plate_text_display = format_indian_plate(cand_norm)
                    break

            if not plate_text_display:
                guessed = guess_india_plate(plate_text_raw)
                if not guessed:
                    for cand in candidates:
                        guessed = guess_india_plate(cand)
                        if guessed:
                            break
                if guessed:
                    plate_text_display = guessed
                    guessed_plate = True

            if not plate_text_display:
                results_out.append(
                    RecognizedPlate(
                        camera_id=self.camera_id,
                        bbox=bbox,
                        plate_text="",
                        confidence=float(det_conf),
                        timestamp_utc=timestamp_iso,
                        zone_id=zone_id,
                        det_conf=float(det_conf),
                        ocr_conf=float(ocr_conf),
                        match_status="NO_OCR",
                    )
                )
                continue

            norm_plate = normalize_plate_text(plate_text_display)
            combined_conf = float(det_conf) * float(ocr_conf)

            voted_plate, voted_conf = self._vote_plate(zone_id, plate_text_display, combined_conf, now_utc)
            plate_text_display = voted_plate
            norm_plate = normalize_plate_text(plate_text_display)
            combined_conf = float(voted_conf)

            direction = self._infer_direction(norm_plate, bbox, now_utc)

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
                    )
                )
                continue

            # --- STATUS DECISION ---
            rule_id = None
            promoted_guess = False
            if guessed_plate and self._guess_can_promote(zone_id, norm_plate, combined_conf, now_utc):
                guessed_plate = False
                promoted_guess = True

            if guessed_plate:
                match_status, event_type, severity = ("GUESSED", "ANPR_PLATE_DETECTED", "info")
            else:
                match_status, event_type, severity = decide_plate_status(
                    norm_plate,
                    self.whitelist_plates,
                    self.blacklist_plates,
                )

            # Time Window overrides event type
            if not inside_time:
                event_type = "ANPR_TIME_VIOLATION"
                severity = "warning"

            extra = {
                "ocr_conf": f"{float(ocr_conf):.4f}",
                "det_conf": f"{float(det_conf):.4f}",
                "rules_json": "1" if (self.whitelist_plates or self.blacklist_plates) else "0",
                "inside_time": "1" if inside_time else "0",
                "frame_index": str(self.frame_index),
            }
            if guessed_plate:
                extra["guessed"] = "1"
            if promoted_guess:
                extra["guess_promoted"] = "1"
            if self.registered_plates:
                extra["registered"] = "1" if norm_plate in self.registered_plates else "0"

            event_id = str(uuid.uuid4())
            image_url = None
            if snapshotter is not None and frame is not None:
                try:
                    image_url = snapshotter(
                        frame,
                        event_id,
                        now_utc,
                        bbox=bbox,
                        label=f"Plate: {plate_text_display}",
                    )
                except Exception:
                    image_url = None

            event = EventModel(
                godown_id=self.godown_id,
                camera_id=self.camera_id,
                event_id=event_id,
                event_type=event_type,
                severity=severity,
                timestamp_utc=timestamp_iso,
                bbox=bbox,
                track_id=0,
                image_url=image_url,
                clip_url=None,
                meta=MetaModel(
                    zone_id=zone_id if zone_id != "__GLOBAL__" else None,
                    rule_id=rule_id or "",
                    confidence=combined_conf,
                    plate_text=plate_text_display,
                    match_status=match_status,
                    direction=direction,
                    extra=extra,
                ),
            )
            mqtt_client.publish_event(event)
            self._update_cache(norm_plate, zone_id, now_utc)

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
                )
            )

            self.logger.info(
                "ANPR: plate=%s zone=%s direction=%s time_ok=%s status=%s event=%s",
                plate_text_display, zone_id, direction, inside_time,
                match_status, event_type
            )

        return results_out
