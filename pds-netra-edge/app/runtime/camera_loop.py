"""
Camera loop for processing individual video sources.

This module defines a function that starts a dedicated thread for each
camera configured in the system. Each thread runs a ``Pipeline``
instance that performs detection and invokes a user-defined callback.

Merged version: combines both variants you shared, with safe fallbacks
for repo-to-repo signature differences (RulesEvaluator / ANPR / snapshots / watchlist).
"""

from __future__ import annotations

import threading
import logging
import os
import urllib.request
import numpy as np
from pathlib import Path
import time
import json
import datetime
import inspect
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple


# ---------------------------------------------------------------------
# Compatibility helpers (different repos may have different ctor signatures)
# ---------------------------------------------------------------------

def _safe_kw(obj: Any, key: str, default: Any = None) -> Any:
    return getattr(obj, key, default) if obj is not None else default


def _init_watchlist_processor(
    camera_id: str,
    godown_id: str,
    mqtt_client: MQTTClient,
    watchlist_manager: WatchlistManager,
    watchlist_cfg: Any,
    logger: logging.Logger,
) -> Optional[WatchlistProcessor]:
    """Create WatchlistProcessor across differing signatures."""
    try:
        sig = inspect.signature(WatchlistProcessor)  # type: ignore[arg-type]
        params = sig.parameters

        kwargs: Dict[str, Any] = {}
        if "camera_id" in params:
            kwargs["camera_id"] = camera_id
        if "godown_id" in params:
            kwargs["godown_id"] = godown_id
        if "manager" in params:
            kwargs["manager"] = watchlist_manager
        if "mqtt_client" in params or "mqtt" in params:
            kwargs["mqtt_client" if "mqtt_client" in params else "mqtt"] = mqtt_client

        # config knobs
        min_conf = _safe_kw(watchlist_cfg, "min_confidence", _safe_kw(watchlist_cfg, "min_conf", 0.75))
        cooldown = _safe_kw(watchlist_cfg, "cooldown_seconds", _safe_kw(watchlist_cfg, "cooldown", 10))
        if "min_confidence" in params:
            kwargs["min_confidence"] = min_conf
        if "cooldown_seconds" in params:
            kwargs["cooldown_seconds"] = cooldown

        return WatchlistProcessor(**kwargs)  # type: ignore[misc]
    except TypeError as e:
        # Signature mismatch; don't crash the whole camera loop
        logger.exception("Failed to init WatchlistProcessor (signature mismatch): %s", e)
        return None
    except Exception:
        logger.exception("Failed to init WatchlistProcessor")
        return None


def _safe_call(fn, *args, **kwargs):
    """Call a function that may accept different param sets."""
    try:
        return fn(*args, **kwargs)
    except TypeError:
        # Try dropping unexpected kwargs
        if kwargs:
            sig = inspect.signature(fn)
            allowed = set(sig.parameters.keys())
            filtered = {k: v for k, v in kwargs.items() if k in allowed}
            return fn(*args, **filtered)
        raise

from ..cv.pipeline import Pipeline, DetectedObject
from ..cv.bag_movement import BagMovementProcessor
from ..cv.yolo_detector import YoloDetector
from ..events.mqtt_client import MQTTClient
from ..rules.loader import (
    load_rules,
    AnprMonitorRule,
    AnprWhitelistRule,
    AnprBlacklistRule,
    BagMonitorRule,
    BagOddHoursRule,
    BagUnplannedRule,
    BagTallyMismatchRule,
    BaseRule,
)
from ..rules.evaluator import RulesEvaluator
from ..cv.anpr import AnprProcessor, PlateDetector, RecognizedPlate
from ..rules.remote import fetch_rule_configs
from ..cv.tamper import analyze_frame_for_tamper, CameraTamperState
from ..config import Settings, HealthConfig, FaceRecognitionCameraConfig, CameraConfig, ZoneConfig, CameraModules
from ..cv.face_id import FaceRecognitionProcessor, FaceOverlay, load_known_faces, detect_faces
from ..cv.fire_detection import FireDetectionProcessor
from ..watchlist.manager import WatchlistManager
from ..watchlist.processor import WatchlistProcessor
from ..watchlist.sync_subscriber import WatchlistSyncSubscriber
from ..presence.processor import AfterHoursPresenceProcessor, PresenceConfig
from ..overrides import EdgeOverrideManager
from ..snapshots import default_snapshot_writer
from ..annotated_video import AnnotatedVideoWriter, LiveFrameWriter
from .pipeline_router import select_pipeline


@dataclass
class CameraHealthState:
    """Mutable state for camera health and tamper monitoring."""
    started_at_utc: Optional[datetime.datetime] = None
    last_frame_utc: Optional[datetime.datetime] = None
    last_frame_monotonic: Optional[float] = None
    fps_estimate: Optional[float] = None
    fps_degraded: bool = False
    is_online: bool = False
    offline_reported: bool = False
    last_tamper_reason: Optional[str] = None
    last_tamper_time: Optional[datetime.datetime] = None
    last_event_by_reason: Dict[str, datetime.datetime] = field(default_factory=dict)
    tamper_state: CameraTamperState = field(default_factory=CameraTamperState)
    suppress_offline_events: bool = False


class NullDetector:
    """Lightweight detector that yields no detections (used for ANPR/health-only cameras)."""
    def track(self, frame):  # type: ignore[no-untyped-def]
        return []


def start_camera_loops(
    settings: Settings,
    mqtt_client: MQTTClient,
    device: str = "cpu",
) -> Tuple[list[threading.Thread], Dict[str, CameraHealthState]]:
    """
    Start processing threads for each configured camera.
    """
    logger = logging.getLogger("camera_loop")
    threads: list[threading.Thread] = []
    camera_states: Dict[str, CameraHealthState] = {}
    camera_lock = threading.Lock()
    rules_lock = threading.Lock()
    started_cameras: set[str] = set()

    # ---------- Override source (test vs live) ----------
    override_path = os.getenv("EDGE_OVERRIDE_PATH")
    if not override_path:
        override_dir = os.getenv(
            "EDGE_OVERRIDE_DIR",
            str(Path(__file__).resolve().parents[3] / "pds-netra-backend" / "data" / "edge_overrides"),
        )
        override_path = str(Path(override_dir) / f"{settings.godown_id}.json")
    override_manager = EdgeOverrideManager(override_path, refresh_interval=5)
    if override_path and Path(override_path).exists():
        logger.info("Edge override path: %s", override_path)

    # ---------- Watchlist Manager ----------
    watchlist_manager: Optional[WatchlistManager] = None
    watchlist_subscriber: Optional[WatchlistSyncSubscriber] = None
    if getattr(settings, "watchlist", None) and settings.watchlist.enabled:
        backend_url = os.getenv("EDGE_BACKEND_URL", "http://127.0.0.1:8001")
        cache_dir = Path(
            os.getenv(
                "EDGE_WATCHLIST_DIR",
                str(Path(__file__).resolve().parents[3] / "data" / "watchlist"),
            )
        )
        watchlist_manager = WatchlistManager(
            backend_url=backend_url,
            cache_dir=cache_dir,
            sync_interval_sec=settings.watchlist.sync_interval_sec,
            auto_embed=settings.watchlist.auto_embed,
            auth_token=os.getenv("EDGE_BACKEND_TOKEN"),
        )
        watchlist_manager.start()
        watchlist_subscriber = WatchlistSyncSubscriber(settings, watchlist_manager)
        watchlist_subscriber.start()

    # Load all rules once
    all_rules = load_rules(settings)

    @dataclass
    class CameraProcessors:
        evaluator: Optional[RulesEvaluator]
        bag_processor: Optional[BagMovementProcessor]
        anpr_processor: Optional[AnprProcessor]
        detector: Any
        anpr_detector: Optional[YoloDetector]
        zone_polygons: dict[str, list[tuple[int, int]]]

    processors: Dict[str, CameraProcessors] = {}

    # -------------------- Helpers --------------------
    def _read_bool_env(name: str, default: str = "false") -> bool:
        return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y"}

    def _read_int_env(name: str, default: int) -> int:
        try:
            return int(os.getenv(name, str(default)))
        except Exception:
            return default

    def _read_float_env(name: str, default: float) -> float:
        try:
            return float(os.getenv(name, str(default)))
        except Exception:
            return default

    def _read_str_env(name: str) -> Optional[str]:
        val = os.getenv(name)
        if val and val.strip():
            return val.strip()
        return None

    def _call_default_snapshot_writer(godown_id: str, camera_id: str):
        """
        Different repos have different signatures:
        - default_snapshot_writer() -> callable
        - default_snapshot_writer(godown_id, camera_id) -> callable
        """
        try:
            sig = inspect.signature(default_snapshot_writer)
            params = list(sig.parameters.values())
            non_self = [p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
            if len(non_self) == 0:
                return default_snapshot_writer()
            if len(non_self) >= 2:
                return default_snapshot_writer(godown_id, camera_id)
            return default_snapshot_writer()
        except Exception:
            try:
                return default_snapshot_writer(godown_id, camera_id)
            except Exception:
                return default_snapshot_writer()

    def _is_file_source(src: str) -> bool:
        """Return True if the pipeline source looks like a local video file path."""
        if not src:
            return False
        s = str(src).strip()
        if not s:
            return False
        s_lower = s.lower()
        if s_lower.startswith(("rtsp://", "rtsps://", "http://", "https://")):
            return False
        if (len(s) >= 2 and s[1] == ":") or s.startswith("\\\\"):
            return True
        if s.startswith("/"):
            return True
        media_exts = (".mp4", ".avi", ".mkv", ".mov", ".m4v", ".ts", ".webm", ".mjpeg")
        if s_lower.endswith(media_exts):
            return True
        try:
            if Path(s).expanduser().exists():
                return True
        except Exception:
            pass
        return False

    def _resolve_anpr_model_path() -> str:
        env_path = _read_str_env("EDGE_ANPR_MODEL")
        if env_path:
            return env_path
        candidates = [
            str(Path("ML_Model") / "anpr.pt"),
            str(Path(".") / "ML_Model" / "anpr.pt"),
            "anpr.pt",
            "platemodel.pt",
            "platemodel",
        ]
        for p in candidates:
            try:
                if Path(p).exists():
                    return p
            except Exception:
                continue
        return "ML_Model/anpr.pt"

    def _build_anpr_detector() -> YoloDetector:
        anpr_model_path = _resolve_anpr_model_path()
        anpr_imgsz = _read_int_env("EDGE_ANPR_IMGSZ", 960)
        anpr_conf = _read_float_env("EDGE_ANPR_CONF", 0.35)
        anpr_iou = _read_float_env("EDGE_ANPR_IOU", 0.45)
        anpr_max_det = _read_int_env("EDGE_ANPR_MAX_DET", 300)

        anpr_classes_raw = os.getenv("EDGE_ANPR_CLASSES", "0").strip()
        anpr_classes = None
        if anpr_classes_raw:
            try:
                anpr_classes = [int(x.strip()) for x in anpr_classes_raw.split(",") if x.strip() != ""]
            except Exception:
                anpr_classes = [0]

        return YoloDetector(
            model_name=anpr_model_path,
            device=device,
            tracker_name=settings.tracking.tracker_name,
            track_persist=settings.tracking.track_persist,
            track_conf=settings.tracking.conf,
            track_iou=settings.tracking.iou,
            conf=anpr_conf,
            iou=anpr_iou,
            imgsz=anpr_imgsz,
            classes=anpr_classes,
            max_det=anpr_max_det,
        )

    def _resolve_general_model_cfg() -> tuple[str, Optional[float], Optional[float], Optional[int], Any, Optional[int]]:
        model_name = (
            getattr(settings, "model_path", None)
            or getattr(settings, "yolo_model_path", None)
            or getattr(getattr(settings, "yolo", None), "model_path", None)
            or getattr(getattr(settings, "model", None), "path", None)
            or os.getenv("EDGE_MODEL_PATH")
            or os.getenv("EDGE_MODEL")
            or "./animal.pt"
        )
        model_conf = (
            getattr(settings, "model_conf", None)
            or getattr(settings, "conf", None)
            or getattr(getattr(settings, "yolo", None), "conf", None)
            or _read_float_env("EDGE_MODEL_CONF", 0.35)
        )
        model_iou = (
            getattr(settings, "model_iou", None)
            or getattr(settings, "iou", None)
            or getattr(getattr(settings, "yolo", None), "iou", None)
            or _read_float_env("EDGE_MODEL_IOU", 0.45)
        )
        model_imgsz = (
            getattr(settings, "model_imgsz", None)
            or getattr(settings, "imgsz", None)
            or getattr(getattr(settings, "yolo", None), "imgsz", None)
            or _read_int_env("EDGE_MODEL_IMGSZ", 640)
        )
        model_classes = (
            getattr(settings, "model_classes", None)
            or getattr(settings, "classes", None)
            or getattr(getattr(settings, "yolo", None), "classes", None)
        )
        model_max_det = (
            getattr(settings, "model_max_det", None)
            or getattr(settings, "max_det", None)
            or getattr(getattr(settings, "yolo", None), "max_det", None)
        )
        try:
            if model_max_det is not None:
                model_max_det = int(model_max_det)
        except Exception:
            model_max_det = None
        return (
            str(model_name),
            float(model_conf) if model_conf is not None else None,
            float(model_iou) if model_iou is not None else None,
            int(model_imgsz) if model_imgsz is not None else None,
            model_classes,
            model_max_det,
        )

    def _build_rules_evaluator(camera_id: str, zone_polygons: dict[str, list[tuple[int, int]]], rules: List[BaseRule]) -> Optional[RulesEvaluator]:
        # Try "new" evaluator signature (rich params), else fallback to "old" signature.
        try:
            return RulesEvaluator(
                camera_id=camera_id,
                godown_id=settings.godown_id,
                rules=rules,
                zone_polygons=zone_polygons,
                timezone=settings.timezone,
                alert_on_person=_read_bool_env("EDGE_ALERT_ON_PERSON", "false"),
                person_alert_cooldown_sec=_read_int_env("EDGE_ALERT_PERSON_COOLDOWN", 10),
                alert_classes=[c.strip() for c in os.getenv("EDGE_ALERT_ON_CLASSES", "").split(",") if c.strip()],
                alert_severity=os.getenv("EDGE_ALERT_SEVERITY", "warning"),
                alert_min_conf=_read_float_env("EDGE_ALERT_MIN_CONF", 0.0),
                zone_enforce=_read_bool_env("EDGE_ZONE_ENFORCE", "true"),
            )
        except TypeError:
            try:
                return RulesEvaluator(camera_id, settings.godown_id, settings.timezone, mqtt_client, rules)  # type: ignore[arg-type]
            except Exception:
                return None
        except Exception:
            return None

    def _run_rules_evaluator(evaluator: RulesEvaluator, objects: List[DetectedObject], frame, now_utc: datetime.datetime, meta_extra: dict[str, str]) -> None:
        # Prefer new method if present
        if hasattr(evaluator, "process_detections"):
            evaluator.process_detections(  # type: ignore[attr-defined]
                objects=objects,
                now_utc=now_utc,
                mqtt_client=mqtt_client,
                frame=frame,
                snapshotter=None,
                instant_only=False,
                meta_extra=meta_extra,
            )
            return
        # Fallback older method
        if hasattr(evaluator, "process"):
            try:
                evaluator.process(objects, frame=frame)  # type: ignore[misc]
            except TypeError:
                evaluator.process(objects)  # type: ignore[misc]

    def _update_rules_evaluator(evaluator: RulesEvaluator, rules: List[BaseRule]) -> None:
        if hasattr(evaluator, "update_rules"):
            evaluator.update_rules(rules)  # type: ignore[misc]

    def _build_anpr_processor(
        camera_id: str,
        zone_polygons: dict[str, list[tuple[int, int]]],
        anpr_rules: List[BaseRule],
        anpr_detector: YoloDetector,
    ) -> Optional[AnprProcessor]:
        plate_detector = PlateDetector(
            anpr_detector,
            plate_class_names=getattr(getattr(settings, "anpr", None), "plate_class_names", None),
        )
        # Try most common variants
        try:
            return AnprProcessor(
                camera_id=camera_id,
                godown_id=settings.godown_id,
                rules=anpr_rules,
                zone_polygons=zone_polygons,
                timezone=settings.timezone,
                plate_detector=plate_detector,
                ocr_lang=getattr(getattr(settings, "anpr", None), "ocr_lang", None),
                ocr_every_n=getattr(getattr(settings, "anpr", None), "ocr_every_n", 1),
                ocr_min_conf=getattr(getattr(settings, "anpr", None), "ocr_min_conf", 0.3),
                ocr_debug=getattr(getattr(settings, "anpr", None), "ocr_debug", False),
                validate_india=getattr(getattr(settings, "anpr", None), "validate_india", False),
                show_invalid=getattr(getattr(settings, "anpr", None), "show_invalid", False),
                registered_file=getattr(getattr(settings, "anpr", None), "registered_file", None),
                save_csv=getattr(getattr(settings, "anpr", None), "save_csv", None),
                save_crops_dir=getattr(getattr(settings, "anpr", None), "save_crops_dir", None),
                save_crops_max=getattr(getattr(settings, "anpr", None), "save_crops_max", None),
                dedup_interval_sec=getattr(getattr(settings, "anpr", None), "dedup_interval_sec", 30),
            )
        except TypeError:
            try:
                return AnprProcessor(camera_id, settings.godown_id, settings.timezone, anpr_rules, plate_detector, zone_polygons)
            except TypeError:
                try:
                    return AnprProcessor(
                        camera_id=camera_id,
                        godown_id=settings.godown_id,
                        mqtt_client=mqtt_client,
                        timezone=settings.timezone,
                        rules=anpr_rules,
                        plate_detector=plate_detector,
                    )
                except Exception:
                    return None

    def _update_anpr_processor(proc: AnprProcessor, rules: List[BaseRule]) -> None:
        if hasattr(proc, "update_rules"):
            try:
                proc.update_rules(rules)  # type: ignore[misc]
            except Exception:
                pass

    def _start_camera(camera: CameraConfig) -> None:
        with camera_lock:
            if camera.id in started_cameras:
                return
            started_cameras.add(camera.id)

        default_source = camera.rtsp_url
        if getattr(camera, "test_video", None):
            test_path = Path(camera.test_video).expanduser()
            resolved_test = test_path if test_path.is_absolute() else (Path.cwd() / test_path).resolve()
            if resolved_test.exists():
                default_source = str(resolved_test)
            else:
                logger.warning("Test video not found for camera %s: %s (falling back to rtsp)", camera.id, resolved_test)

        pipeline_spec = select_pipeline(camera, settings)
        modules = pipeline_spec.modules
        logger.info("Camera routing: camera=%s role=%s modules=%s", camera.id, pipeline_spec.role, modules)

        # Main detector
        detector: Any
        need_general_detector = modules.animal_detection_enabled or modules.person_after_hours_enabled
        if need_general_detector:
            try:
                model_name, model_conf, model_iou, model_imgsz, model_classes, model_max_det = _resolve_general_model_cfg()
                detector = YoloDetector(
                    model_name=model_name,
                    device=device,
                    tracker_name=settings.tracking.tracker_name,
                    track_persist=settings.tracking.track_persist,
                    track_conf=settings.tracking.conf,
                    track_iou=settings.tracking.iou,
                    conf=model_conf,
                    iou=model_iou,
                    imgsz=model_imgsz,
                    classes=model_classes,
                    max_det=model_max_det,
                )
            except Exception:
                logger.exception("Failed to init YoloDetector for %s, using NullDetector", camera.id)
                detector = NullDetector()
        else:
            detector = NullDetector()

        # Per-camera health state
        state = CameraHealthState(
            started_at_utc=datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc),
            is_online=False,
            offline_reported=False,
        )
        camera_states[camera.id] = state

        # Zones
        zone_polygons: dict[str, list[tuple[int, int]]] = {}
        if getattr(camera, "zones", None):
            for z in camera.zones:
                if z and z.id and isinstance(z.polygon, list):
                    try:
                        zone_polygons[z.id] = [(int(p[0]), int(p[1])) for p in z.polygon]
                    except Exception:
                        pass

        # Rules evaluator / bag processor
        evaluator: Optional[RulesEvaluator] = None
        bag_processor: Optional[BagMovementProcessor] = None

        typed_rules: List[BaseRule] = [r for r in all_rules if isinstance(r, BaseRule)]
        cam_rules: List[BaseRule] = [r for r in typed_rules if r.camera_id == camera.id]

        bag_rules = [r for r in cam_rules if isinstance(r, (BagMonitorRule, BagOddHoursRule, BagUnplannedRule, BagTallyMismatchRule))]
        if cam_rules and need_general_detector:
            evaluator = _build_rules_evaluator(camera.id, zone_polygons, cam_rules)

        if bag_rules and modules.animal_detection_enabled:
            try:
                bag_processor = BagMovementProcessor(
                    camera.id,
                    settings.godown_id,
                    zone_polygons,
                    bag_rules,
                    settings.timezone,
                    settings.dispatch_plan_path,
                    settings.dispatch_plan_reload_sec,
                    settings.bag_class_keywords,
                )
            except TypeError:
                bag_processor = BagMovementProcessor(camera.id, settings.godown_id, zone_polygons, bag_rules, settings.timezone)

        # ANPR
        anpr_detector: Optional[YoloDetector] = None
        anpr_processor: Optional[AnprProcessor] = None
        if modules.anpr_enabled or modules.gate_entry_exit_enabled:
            try:
                anpr_detector = _build_anpr_detector()
                anpr_rules = [r for r in cam_rules if isinstance(r, (AnprMonitorRule, AnprWhitelistRule, AnprBlacklistRule))]
                anpr_processor = _build_anpr_processor(camera.id, zone_polygons, anpr_rules, anpr_detector)
            except Exception:
                logger.exception("Failed to init ANPR for camera %s", camera.id)
                anpr_detector = None
                anpr_processor = None

        processors[camera.id] = CameraProcessors(
            evaluator=evaluator,
            bag_processor=bag_processor,
            anpr_processor=anpr_processor,
            detector=detector,
            anpr_detector=anpr_detector,
            zone_polygons=zone_polygons,
        )

        # Optional processors
        face_processor: Optional[FaceRecognitionProcessor] = None
        watchlist_processor: Optional[WatchlistProcessor] = None
        presence_processor: Optional[AfterHoursPresenceProcessor] = None
        fire_processor: Optional[FireDetectionProcessor] = None

        # Face recognition
        if hasattr(camera, "face_recognition") and camera.face_recognition and camera.face_recognition.enabled:
            try:
                fr_cfg: FaceRecognitionCameraConfig = camera.face_recognition
                known_faces = load_known_faces(fr_cfg.known_faces_dir)
                face_processor = FaceRecognitionProcessor(camera.id, settings.godown_id, mqtt_client, known_faces, fr_cfg)
            except Exception:
                logger.exception("Failed to init FaceRecognitionProcessor for %s", camera.id)

        # WatchlistProcessor signature differs across repos
        if watchlist_manager and getattr(settings, "watchlist", None) and settings.watchlist.enabled:
            watchlist_processor = _init_watchlist_processor(
                camera_id=camera.id,
                godown_id=settings.godown_id,
                mqtt_client=mqtt_client,
                watchlist_manager=watchlist_manager,
                watchlist_cfg=settings.watchlist,
                logger=logger,
            )

        # Presence processor (may be absent)
        if modules.person_after_hours_enabled and hasattr(settings, "after_hours") and settings.after_hours:
            try:
                pcfg = PresenceConfig(
                    start_time=settings.after_hours.start_time,
                    end_time=settings.after_hours.end_time,
                    cooldown_sec=settings.after_hours.cooldown_sec,
                    min_confidence=settings.after_hours.min_confidence,
                )
                presence_processor = AfterHoursPresenceProcessor(camera.id, settings.godown_id, mqtt_client, pcfg, settings.timezone)
            except Exception:
                logger.exception("Failed to init AfterHoursPresenceProcessor for %s", camera.id)
                presence_processor = None

        if modules.fire_detection_enabled:
            try:
                fire_processor = FireDetectionProcessor(camera.id, settings.godown_id, mqtt_client, settings.fire_detection)
            except Exception:
                logger.exception("Failed to init FireDetectionProcessor for %s", camera.id)
                fire_processor = None

        # Snapshot writer (signature differs)
        try:
            snapshot_writer = _call_default_snapshot_writer(settings.godown_id, camera.id)
        except Exception:
            snapshot_writer = None

        detect_classes = getattr(settings, "model_class_names", None) or None
        health_cfg: Optional[HealthConfig] = (getattr(settings, 'health', None) if modules.health_monitoring_enabled else None)

        def camera_runner(
            camera_obj: CameraConfig,
            default_src: str,
            processors_local: CameraProcessors,
            face_proc: Optional[FaceRecognitionProcessor],
            watch_proc: Optional[WatchlistProcessor],
            presence_proc: Optional[AfterHoursPresenceProcessor],
            fire_proc: Optional[FireDetectionProcessor],
            health_config: Optional[HealthConfig],
            state_local: CameraHealthState,
            detector_local: Any,
            snapshot_writer_local,
            class_filter: Optional[List[str]],
            health_enabled_local: bool,
        ):
            current_state = {"mode": "live", "run_id": None}

            annotated_writer: Optional[AnnotatedVideoWriter] = None
            live_writer: Optional[LiveFrameWriter] = None
            if os.getenv("EDGE_LIVE_FRAMES", "true").lower() == "true":
                try:
                    live_dir = os.getenv("EDGE_LIVE_ANNOTATED_DIR") or os.getenv("EDGE_LIVE_DIR")
                    if not live_dir:
                        live_dir = str(
                            Path(__file__).resolve().parents[3]
                            / "pds-netra-backend"
                            / "data"
                            / "live"
                        )
                    live_path = Path(live_dir) / settings.godown_id / f"{camera_obj.id}_latest.jpg"
                    live_writer = LiveFrameWriter(str(live_path))
                except Exception:
                    live_writer = None

            def _resolve_source_local() -> tuple[str, str, Optional[str]]:
                return override_manager.get_camera_source(camera_obj.id, default_src)

            def callback(objects: List[DetectedObject], frame=None):
                now_utc = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
                state_local.last_frame_utc = now_utc
                state_local.last_frame_monotonic = time.monotonic()
                state_local.is_online = True

                face_overlays: list[FaceOverlay] = []
                if face_proc:
                    try:
                        face_overlays = detect_faces(frame, face_proc)
                    except Exception:
                        pass

                if presence_proc:
                    try:
                        presence_proc.process(frame, objects)
                    except Exception:
                        pass

                if watch_proc and hasattr(watch_proc, "process"):
                    try:
                        watch_proc.process(frame, objects, face_overlays)  # type: ignore[misc]
                    except TypeError:
                        try:
                            watch_proc.process(frame, objects)  # type: ignore[misc]
                        except Exception:
                            pass
                    except Exception:
                        pass

                if fire_proc:
                    try:
                        fire_proc.process(frame)
                    except Exception:
                        pass

                if processors_local.evaluator:
                    try:
                        _run_rules_evaluator(
                            processors_local.evaluator,
                            objects=objects,
                            frame=frame,
                            now_utc=now_utc,
                            meta_extra={
                                "mode": str(current_state.get("mode") or ""),
                                "run_id": str(current_state.get("run_id") or ""),
                            },
                        )
                    except Exception:
                        logger.exception("RulesEvaluator failed for camera=%s", camera_obj.id)

                last_anpr: list[RecognizedPlate] = []
                if processors_local.anpr_processor and processors_local.anpr_detector:
                    try:
                        if hasattr(processors_local.anpr_processor, "process_frame"):
                            last_anpr = processors_local.anpr_processor.process_frame(frame, now_utc, mqtt_client)
                        else:
                            last_anpr = processors_local.anpr_processor.process(frame)  # type: ignore[attr-defined]
                    except Exception:
                        logger.exception("ANPR processing failed for camera=%s", camera_obj.id)

                if health_config and health_enabled_local:
                    try:
                        analyze_frame_for_tamper(
                            frame=frame,
                            camera_id=camera_obj.id,
                            godown_id=settings.godown_id,
                            mqtt_client=mqtt_client,
                            tz=settings.timezone,
                            config=health_config,
                            state=state_local.tamper_state,
                            last_event_by_reason=state_local.last_event_by_reason,
                        )
                    except Exception:
                        pass

                if snapshot_writer_local:
                    try:
                        try:
                            snapshot_writer_local(frame, objects)
                        except TypeError:
                            snapshot_writer_local(frame)
                    except Exception:
                        pass

                # Draw overlays and write
                if frame is not None:
                    dets = [(o.class_name, o.confidence, o.bbox, o.track_id) for o in objects]
                    try:
                        import cv2
                        for zid, poly in processors_local.zone_polygons.items():
                            pts = np.array([(int(x), int(y)) for x, y in poly], np.int32)
                            cv2.polylines(frame, [pts], True, (255, 150, 0), 2)
                            cv2.putText(
                                frame,
                                zid,
                                (pts[0][0], max(pts[0][1] - 6, 10)),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.6,
                                (255, 150, 0),
                                2,
                            )

                        for rp in last_anpr:
                            x1, y1, x2, y2 = rp.bbox
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
                            txt = f"{rp.plate_text} ({rp.zone_id})" if (rp.zone_id and rp.zone_id != "__GLOBAL__") else rp.plate_text
                            cv2.putText(frame, txt or "PLATE", (x1, max(y1 - 8, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

                        for face in face_overlays:
                            if face.bbox:
                                lbl = face.person_name if (face.status == "KNOWN" and face.person_name) else "Face"
                                dets.append((lbl, float(face.confidence or 1.0), face.bbox, -1))
                    except Exception:
                        pass

                    if annotated_writer:
                        annotated_writer.write_frame(frame, dets)
                    if live_writer:
                        live_writer.write_frame(frame, dets)

            def bag_handler(objects, now_utc, frame):  # type: ignore[no-untyped-def]
                if processors_local.bag_processor:
                    try:
                        processors_local.bag_processor.process(objects, frame=frame)
                    except Exception:
                        pass
                return objects

            while True:
                if not getattr(camera_obj, "is_active", True):
                    if state_local.is_online:
                        logger.info("Camera deactivated: %s", camera_obj.id)
                        state_local.is_online = False
                    time.sleep(5)
                    continue

                src, mode, r_id = _resolve_source_local()
                state_local.suppress_offline_events = not health_enabled_local
                current_state.update({"mode": mode, "run_id": r_id})
                if mode == "test":
                    state_local.suppress_offline_events = True

                if _is_file_source(src):
                    res = Path(src).expanduser().resolve()
                    if not res.exists():
                        logger.warning("Test video missing: %s", res)
                        src, mode, r_id = camera_obj.rtsp_url, "live", None
                        current_state.update({"mode": mode, "run_id": r_id})
                    else:
                        src = str(res)

                logger.info("Pipeline starting for %s (mode=%s, source=%s)", camera_obj.id, mode, src)

                annotated_writer = None
                if mode == "test" and r_id:
                    a_dir = Path(
                        os.getenv(
                            "EDGE_ANNOTATED_DIR",
                            str(Path(__file__).resolve().parents[3] / "pds-netra-backend" / "data" / "annotated"),
                        )
                    )
                    a_path = a_dir / settings.godown_id / r_id / f"{camera_obj.id}.mp4"
                    l_path = a_dir / settings.godown_id / r_id / f"{camera_obj.id}_latest.jpg"
                    annotated_writer = AnnotatedVideoWriter(str(a_path), latest_path=str(l_path), latest_interval=0.2)

                def should_stop() -> bool:
                    if not getattr(camera_obj, "is_active", True):
                        return True
                    d_src, _d_mode, _d_rid = _resolve_source_local()
                    return d_src != src

                Pipeline(
                    src,
                    camera_obj.id,
                    detector_local,
                    callback,
                    stop_check=should_stop,
                    frame_processors=[bag_handler],
                ).run()

                if annotated_writer:
                    annotated_writer.close()

                if mode == "test":
                    state_local.suppress_offline_events = True
                    logger.info("Test run completed for %s (run_id=%s)", camera_obj.id, r_id)
                    if r_id:
                        try:
                            m_dir = Path(
                                os.getenv(
                                    "EDGE_ANNOTATED_DIR",
                                    str(Path(__file__).resolve().parents[3] / "pds-netra-backend" / "data" / "annotated"),
                                )
                            )
                            marker = m_dir / settings.godown_id / r_id / "completed.json"
                            marker.parent.mkdir(parents=True, exist_ok=True)
                            marker.write_text(
                                json.dumps(
                                    {"run_id": r_id, "camera_id": camera_obj.id, "completed_at": datetime.datetime.utcnow().isoformat() + "Z"},
                                    indent=2,
                                )
                            )
                        except Exception:
                            pass
                break

        t = threading.Thread(
            target=camera_runner,
            args=(
                camera,
                default_source,
                processors[camera.id],
                face_processor,
                watchlist_processor,
                presence_processor,
                fire_processor,
                health_cfg,
                state,
                detector,
                snapshot_writer,
                detect_classes,
                modules.health_monitoring_enabled,
            ),
            name=f"Pipeline-{camera.id}",
            daemon=True,
        )
        t.start()
        threads.append(t)

    # Initial start
    for cam in settings.cameras:
        _start_camera(cam)

    # Dynamic Discovery
    if os.getenv("EDGE_DYNAMIC_CAMERAS", "true").lower() == "true":

        def _discover_loop():
            b_url = os.getenv("EDGE_BACKEND_URL", "http://127.0.0.1:8001").rstrip("/")
            while True:
                try:
                    with urllib.request.urlopen(f"{b_url}/api/v1/godowns/{settings.godown_id}", timeout=3) as r:
                        payload = json.loads(r.read().decode("utf-8"))
                        for cam in payload.get("cameras", []):
                            c_id = cam.get("camera_id")
                            if not c_id:
                                continue
                            rtsp = cam.get("rtsp_url") or cam.get("rtsp")
                            if not rtsp:
                                continue

                            zones: list[ZoneConfig] = []
                            z_raw = cam.get("zones_json")
                            if z_raw:
                                try:
                                    z_data = json.loads(z_raw) if isinstance(z_raw, str) else z_raw
                                    if isinstance(z_data, list):
                                        for z in z_data:
                                            if z.get("id") and isinstance(z.get("polygon"), list):
                                                zones.append(ZoneConfig(id=z["id"], polygon=z["polygon"]))
                                except Exception:
                                    pass

                            with camera_lock:
                                existing = next((c for c in settings.cameras if c.id == c_id), None)
                                if existing:
                                    existing.rtsp_url = rtsp
                                    existing.test_video = cam.get("test_video")
                                    existing.is_active = cam.get("is_active", True)
                                    continue

                                if c_id in started_cameras:
                                    continue

                                role = str(cam.get("role") or "SECURITY").upper()
                                m_raw = cam.get("modules")
                                m_cfg = CameraModules(**m_raw) if isinstance(m_raw, dict) else None
                                n_cam = CameraConfig(
                                    id=c_id,
                                    rtsp_url=rtsp,
                                    role=role,
                                    role_explicit=bool(cam.get("role")),
                                    modules=m_cfg,
                                    zones=zones,
                                    test_video=cam.get("test_video"),
                                    is_active=cam.get("is_active", True),
                                )
                                settings.cameras.append(n_cam)
                                _start_camera(n_cam)
                except Exception:
                    pass
                time.sleep(float(os.getenv("EDGE_CAMERA_DISCOVERY_INTERVAL_SEC", "20")))

        threading.Thread(target=_discover_loop, name="CameraDiscovery", daemon=True).start()

    # Rule Sync
    if os.getenv("EDGE_RULES_SOURCE", "backend").lower() == "backend":

        def _apply_rules(upd_rules: list[BaseRule]):
            upd_rules_typed = [r for r in upd_rules if isinstance(r, BaseRule)]
            for c_id, bundle in processors.items():
                c_rules = [r for r in upd_rules_typed if r.camera_id == c_id]
                c_cfg = next((c for c in settings.cameras if c.id == c_id), None)
                mods = select_pipeline(c_cfg, settings).modules if c_cfg else None

                if bundle.evaluator and (mods is None or mods.animal_detection_enabled):
                    _update_rules_evaluator(bundle.evaluator, c_rules)

                b_rules = [r for r in c_rules if isinstance(r, (BagMonitorRule, BagOddHoursRule, BagUnplannedRule, BagTallyMismatchRule))]
                if b_rules and (mods is None or mods.animal_detection_enabled):
                    if bundle.bag_processor and hasattr(bundle.bag_processor, "update_rules"):
                        try:
                            bundle.bag_processor.update_rules(b_rules)  # type: ignore[misc]
                        except Exception:
                            pass
                    else:
                        try:
                            bundle.bag_processor = BagMovementProcessor(
                                c_id,
                                settings.godown_id,
                                bundle.zone_polygons,
                                b_rules,
                                settings.timezone,
                                settings.dispatch_plan_path,
                                settings.dispatch_plan_reload_sec,
                                settings.bag_class_keywords,
                            )
                        except TypeError:
                            bundle.bag_processor = BagMovementProcessor(c_id, settings.godown_id, bundle.zone_polygons, b_rules, settings.timezone)
                else:
                    bundle.bag_processor = None

                a_rules = [r for r in c_rules if isinstance(r, (AnprMonitorRule, AnprWhitelistRule, AnprBlacklistRule))]
                if bundle.anpr_processor:
                    _update_anpr_processor(bundle.anpr_processor, a_rules)

        def _rules_sync_loop():
            b_url = os.getenv("EDGE_BACKEND_URL", "http://127.0.0.1:8001")
            last_sig = None
            while True:
                try:
                    cfgs = fetch_rule_configs(b_url, settings.godown_id)
                    if cfgs is not None:
                        sig = json.dumps([getattr(r, "__dict__", {}) for r in cfgs], sort_keys=True)
                        if sig != last_sig:
                            with rules_lock:
                                settings.rules = cfgs
                                _apply_rules(load_rules(settings))
                                last_sig = sig
                except Exception:
                    pass
                time.sleep(float(os.getenv("EDGE_RULES_SYNC_INTERVAL_SEC", "20")))

        threading.Thread(target=_rules_sync_loop, name="RulesSync", daemon=True).start()

    return threads, camera_states
