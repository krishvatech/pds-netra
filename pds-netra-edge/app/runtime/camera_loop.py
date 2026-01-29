"""
Camera loop for processing individual video sources.

This module defines a function that starts a dedicated thread for each
camera configured in the system. Each thread runs a ``Pipeline``
instance that performs detection and invokes a user-defined callback.
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
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple, Any

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
from ..cv.anpr import AnprProcessor, PlateDetector
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

    # Time when the camera loop was started
    started_at_utc: Optional[datetime.datetime] = None
    # Last UTC time when a frame was successfully processed
    last_frame_utc: Optional[datetime.datetime] = None
    # Monotonic timestamp for FPS estimation
    last_frame_monotonic: Optional[float] = None
    # Smoothed FPS estimate
    fps_estimate: Optional[float] = None
    # Track if FPS is currently below minimum threshold
    fps_degraded: bool = False
    # Flag indicating whether the camera is currently considered online
    is_online: bool = False
    # Flag indicating whether offline event was emitted for current outage
    offline_reported: bool = False
    # Last tamper reason emitted (e.g., "LOW_LIGHT", "LENS_BLOCKED").
    last_tamper_reason: Optional[str] = None
    # Time when the last tamper event was emitted
    last_tamper_time: Optional[datetime.datetime] = None
    # Per-reason cooldown cache
    last_event_by_reason: Dict[str, datetime.datetime] = field(default_factory=dict)
    # Underlying state used by tamper analysis heuristics
    tamper_state: CameraTamperState = field(default_factory=CameraTamperState)
    # Suppress offline events after test run completion
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

    Parameters
    ----------
    settings: Settings
        Loaded application settings containing camera definitions.
    mqtt_client: MQTTClient
        Connected MQTT client used to publish events.
    device: str
        Device specifier for YOLO detector ("cpu" or "cuda").

    Returns
    -------
    List[threading.Thread]
        A list of threads running the pipeline for each camera.
    """
    logger = logging.getLogger("camera_loop")
    threads: list[threading.Thread] = []
    # Dictionary storing mutable health state per camera
    camera_states: Dict[str, CameraHealthState] = {}
    camera_lock = threading.Lock()
    rules_lock = threading.Lock()
    started_cameras: set[str] = set()
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
    watchlist_manager: Optional[WatchlistManager] = None
    watchlist_subscriber: Optional[WatchlistSyncSubscriber] = None
    if settings.watchlist and settings.watchlist.enabled:
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
    # Load all rules once and convert into typed objects
    all_rules = load_rules(settings)

    @dataclass
    class CameraProcessors:
        evaluator: Optional[RulesEvaluator]
        bag_processor: Optional[BagMovementProcessor]
        anpr_processor: Optional[AnprProcessor]
        detector: Any
        zone_polygons: dict[str, list[tuple[int, int]]]

    processors: Dict[str, CameraProcessors] = {}

    def _start_camera(camera: CameraConfig) -> None:
        with camera_lock:
            if camera.id in started_cameras:
                return
            started_cameras.add(camera.id)
        default_source = camera.rtsp_url
        if camera.test_video:
            test_path = Path(camera.test_video).expanduser()
            if test_path.is_absolute():
                resolved_test = test_path
            else:
                resolved_test = (Path.cwd() / test_path).resolve()
            if resolved_test.exists():
                default_source = str(resolved_test)
            else:
                logger.warning(
                    "Test video not found for camera %s: %s (falling back to rtsp)",
                    camera.id,
                    resolved_test,
                )

        pipeline_spec = select_pipeline(camera, settings)
        modules = pipeline_spec.modules
        logger.info("Camera routing: camera=%s role=%s modules=%s", camera.id, pipeline_spec.role, modules)

        # Main detector (animal / general)
        detector: Any
        need_general_detector = modules.animal_detection_enabled or modules.person_after_hours_enabled
        if need_general_detector:
            try:
                model_path = os.getenv("EDGE_YOLO_MODEL", "animal.pt")
                detector = YoloDetector(
                    model_name=model_path,
                    device=device,
                    tracker_name=settings.tracking.tracker_name,
                    track_persist=settings.tracking.track_persist,
                    track_conf=settings.tracking.conf,
                    track_iou=settings.tracking.iou,
                )
            except Exception as exc:
                logger.error("Error loading YOLO detector: %s", exc)
                return
        else:
            detector = NullDetector()
        # Prepare rules and zone polygons for this camera
        camera_rules = [r for r in all_rules if r.camera_id == camera.id]
        zone_polygons: dict[str, list[tuple[int, int]]] = {}
        for zone in camera.zones:
            # Convert lists to tuples for point-in-polygon checks
            zone_polygons[zone.id] = [tuple(pt) for pt in zone.polygon]
        try:
            alert_min_conf = float(os.getenv("EDGE_ALERT_MIN_CONF", "0.5"))
        except ValueError:
            alert_min_conf = 0.5
        detect_classes = {
            c.strip().lower()
            for c in os.getenv("EDGE_DETECT_CLASSES", "").split(",")
            if c.strip()
        }
        evaluator: Optional[RulesEvaluator] = None
        if modules.animal_detection_enabled:
            evaluator = RulesEvaluator(
                camera_id=camera.id,
                godown_id=settings.godown_id,
                rules=camera_rules,
                zone_polygons=zone_polygons,
                timezone=settings.timezone,
                alert_on_person=os.getenv("EDGE_ALERT_ON_PERSON", "false").lower() in {"1", "true", "yes"},
                person_alert_cooldown_sec=int(os.getenv("EDGE_ALERT_PERSON_COOLDOWN", "10")),
                alert_classes=[c.strip() for c in os.getenv("EDGE_ALERT_ON_CLASSES", "").split(",") if c.strip()],
                alert_severity=os.getenv("EDGE_ALERT_SEVERITY", "warning"),
                alert_min_conf=alert_min_conf,
                zone_enforce=os.getenv("EDGE_ZONE_ENFORCE", "true").lower() in {"1", "true", "yes"},
            )
        bag_rules = [
            r
            for r in camera_rules
            if isinstance(r, (BagMonitorRule, BagOddHoursRule, BagUnplannedRule, BagTallyMismatchRule))
        ]
        bag_processor = None
        if bag_rules and modules.animal_detection_enabled:
            bag_processor = BagMovementProcessor(
                camera_id=camera.id,
                godown_id=settings.godown_id,
                zone_polygons=zone_polygons,
                rules=bag_rules,
                timezone=settings.timezone,
                dispatch_plan_path=settings.dispatch_plan_path,
                dispatch_plan_reload_sec=settings.dispatch_plan_reload_sec,
                bag_class_keywords=settings.bag_class_keywords,
                movement_px_threshold=settings.bag_movement_px_threshold,
                movement_time_window_sec=settings.bag_movement_time_window_sec,
            )
        # Determine if ANPR rules apply for this camera
        anpr_rules = [r for r in camera_rules if isinstance(r, (AnprMonitorRule, AnprWhitelistRule, AnprBlacklistRule))]
        anpr_processor: Optional[AnprProcessor] = None
        if settings.anpr is not None and settings.anpr.enabled and modules.anpr_enabled:
            anpr_cfg = settings.anpr
            try:
                gate_line = anpr_cfg.gate_line
                inside_side = anpr_cfg.inside_side
                dedup_interval = anpr_cfg.dedup_interval_sec
                direction_inference = "LINE_CROSSING"
                if camera.anpr is not None:
                    if camera.anpr.gate_line is not None:
                        gate_line = camera.anpr.gate_line
                    if camera.anpr.inside_side is not None:
                        inside_side = camera.anpr.inside_side
                    if camera.anpr.direction_inference:
                        direction_inference = camera.anpr.direction_inference.strip().upper()
                    if camera.anpr.anpr_event_cooldown_seconds is not None:
                        dedup_interval = camera.anpr.anpr_event_cooldown_seconds
                    elif camera.anpr.anpr_event_cooldown_seconds is None:
                        dedup_interval = 10
                if camera.role_explicit and str(camera.role).strip().upper() == "GATE_ANPR" and camera.anpr is None:
                    dedup_interval = 10
                if not modules.gate_entry_exit_enabled:
                    direction_inference = "SESSION_HEURISTIC"
                if direction_inference not in {"LINE_CROSSING", "SESSION_HEURISTIC"}:
                    direction_inference = "LINE_CROSSING"
                if direction_inference == "SESSION_HEURISTIC":
                    gate_line = None

                plate_detector = PlateDetector(
                    YoloDetector(
                        model_name=anpr_cfg.model_path,
                        device=anpr_cfg.device or device,
                        conf=anpr_cfg.conf,
                        iou=anpr_cfg.iou,
                        imgsz=anpr_cfg.imgsz,
                        classes=anpr_cfg.classes,
                        max_det=anpr_cfg.max_det,
                    ),
                    plate_class_names=anpr_cfg.plate_class_names,
                )
                anpr_processor = AnprProcessor(
                    camera_id=camera.id,
                    godown_id=settings.godown_id,
                    rules=anpr_rules,
                    zone_polygons=zone_polygons,
                    timezone=settings.timezone,
                    plate_detector=plate_detector,
                    ocr_engine=None,
                    ocr_lang=anpr_cfg.ocr_lang,
                    ocr_gpu=str(anpr_cfg.device).lower() != "cpu",
                    ocr_every_n=anpr_cfg.ocr_every_n,
                    ocr_min_conf=anpr_cfg.ocr_min_conf,
                    ocr_debug=anpr_cfg.ocr_debug,
                    validate_india=anpr_cfg.validate_india,
                    show_invalid=anpr_cfg.show_invalid,
                    registered_file=anpr_cfg.registered_file,
                    save_csv=anpr_cfg.save_csv,
                    save_crops_dir=anpr_cfg.save_crops_dir,
                    save_crops_max=anpr_cfg.save_crops_max,
                    dedup_interval_sec=dedup_interval,
                    gate_line=gate_line,
                    inside_side=inside_side,
                    direction_max_gap_sec=anpr_cfg.direction_max_gap_sec,
                )
            except Exception as exc:
                logger.error("Failed to initialize ANPR processor for camera %s: %s", camera.id, exc)
                anpr_processor = None
    
        # Initialise health state for this camera
        # Use provided health configuration or a default instance
        health_cfg: HealthConfig
        if camera.health is not None:
            health_cfg = camera.health
        else:
            # Default values will be applied by HealthConfig dataclass
            health_cfg = HealthConfig()
        state = CameraHealthState()
        camera_states[camera.id] = state
        face_watchlist_enabled = modules.animal_detection_enabled or modules.person_after_hours_enabled

        # Face recognition (optional)
        face_processor: Optional[FaceRecognitionProcessor] = None
        fr_cfg = settings.face_recognition
        if fr_cfg is not None and fr_cfg.enabled and face_watchlist_enabled:
            fr_cam_cfg: Optional[FaceRecognitionCameraConfig] = None
            for cam_cfg in fr_cfg.cameras:
                if cam_cfg.camera_id == camera.id:
                    fr_cam_cfg = cam_cfg
                    break
            if fr_cam_cfg is None:
                for cam_cfg in fr_cfg.cameras:
                    if cam_cfg.camera_id in {"*", "all"}:
                        fr_cam_cfg = FaceRecognitionCameraConfig(
                            camera_id=camera.id,
                            zone_id=cam_cfg.zone_id,
                            allow_unknown=cam_cfg.allow_unknown,
                            log_known_only=cam_cfg.log_known_only,
                        )
                        break
            if fr_cam_cfg is None and not fr_cfg.cameras:
                fr_cam_cfg = FaceRecognitionCameraConfig(camera_id=camera.id, zone_id="all")
            if fr_cam_cfg is not None:
                try:
                    known_people = load_known_faces(fr_cfg.known_faces_file)
                    face_processor = FaceRecognitionProcessor(
                        camera_id=camera.id,
                        godown_id=settings.godown_id,
                        camera_config=fr_cam_cfg,
                        global_config=fr_cfg,
                        zone_polygons=zone_polygons,
                        timezone=settings.timezone,
                        known_people=known_people,
                    )
                except Exception as exc:
                    logger.error("Failed to initialize face recognition for camera %s: %s", camera.id, exc)
                    face_processor = None
        watchlist_processor: Optional[WatchlistProcessor] = None
        if watchlist_manager is not None and settings.watchlist and settings.watchlist.enabled and face_watchlist_enabled:
            watchlist_processor = WatchlistProcessor(
                camera_id=camera.id,
                godown_id=settings.godown_id,
                manager=watchlist_manager,
                min_confidence=settings.watchlist.min_match_confidence,
                cooldown_seconds=settings.watchlist.cooldown_seconds,
                zone_polygons=zone_polygons,
                zone_enforce=os.getenv("EDGE_WATCHLIST_ZONE_ENFORCE", "true").lower() in {"1", "true", "yes"},
                http_fallback=settings.watchlist.http_fallback,
            )

        presence_processor: Optional[AfterHoursPresenceProcessor] = None
        if settings.after_hours_presence and settings.after_hours_presence.enabled and modules.person_after_hours_enabled:
            ah_cfg = settings.after_hours_presence
            presence_processor = AfterHoursPresenceProcessor(
                camera_id=camera.id,
                godown_id=settings.godown_id,
                config=PresenceConfig(
                    enabled=ah_cfg.enabled,
                    day_start=ah_cfg.day_start,
                    day_end=ah_cfg.day_end,
                    emit_only_after_hours=ah_cfg.emit_only_after_hours,
                    person_interval_sec=ah_cfg.person_interval_sec,
                    vehicle_interval_sec=ah_cfg.vehicle_interval_sec,
                    person_cooldown_sec=ah_cfg.person_cooldown_sec,
                    vehicle_cooldown_sec=ah_cfg.vehicle_cooldown_sec,
                    min_confidence=ah_cfg.min_confidence,
                    person_classes=ah_cfg.person_classes,
                    vehicle_classes=ah_cfg.vehicle_classes,
                    http_fallback=ah_cfg.http_fallback,
                    timezone=settings.timezone,
                ),
            )

        fire_processor: Optional[FireDetectionProcessor] = None
        if settings.fire_detection and settings.fire_detection.enabled and modules.fire_detection_enabled:
            fire_processor = FireDetectionProcessor(
                camera_id=camera.id,
                godown_id=settings.godown_id,
                config=settings.fire_detection,
                zone_polygons=zone_polygons,
            )
        snapshot_writer = default_snapshot_writer()

        processors[camera.id] = CameraProcessors(
            evaluator=evaluator,
            bag_processor=bag_processor,
            anpr_processor=anpr_processor,
            detector=detector,
            zone_polygons=zone_polygons,
        )
    
        def _is_file_source(source_val: str) -> bool:
            return not (
                source_val.startswith("rtsp://")
                or source_val.startswith("http://")
                or source_val.startswith("https://")
            )
    
        def camera_runner(
            camera_obj,
            default_source_local: str,
            processors_local: CameraProcessors,
            face_processor_local: Optional[FaceRecognitionProcessor],
            watchlist_processor_local: Optional[WatchlistProcessor],
            presence_processor_local: Optional[AfterHoursPresenceProcessor],
            fire_processor_local: Optional[FireDetectionProcessor],
            health_cfg_local: HealthConfig,
            state_local: CameraHealthState,
            detector_local,
            snapshot_writer_local,
            detect_classes_local: set[str],
            health_enabled_local: bool,
        ) -> None:
            annotated_writer: Optional[AnnotatedVideoWriter] = None
            live_writer: Optional[LiveFrameWriter] = None
            current_state = {"mode": "live", "run_id": None, "last_snapshot_ts": 0.0}
            last_zone_sync = 0.0
            zone_sync_interval = float(os.getenv("EDGE_ZONES_SYNC_INTERVAL_SEC", "15"))
            backend_url = os.getenv(
                "EDGE_BACKEND_URL",
                os.getenv("BACKEND_URL", "http://127.0.0.1:8001"),
            ).rstrip("/")
            last_test_video: dict[str, Optional[str]] = {"path": None}

            def _resolve_source_local() -> tuple[str, str, Optional[str]]:
                nonlocal default_source_local
                # Determine "live" fallback dynamically from latest camera_obj state
                live_fallback = camera_obj.rtsp_url or default_source_local
                if camera_obj.test_video:
                    test_path = Path(camera_obj.test_video).expanduser()
                    if test_path.is_absolute():
                        resolved_test = test_path
                    else:
                        resolved_test = (Path.cwd() / test_path).resolve()
                    if resolved_test.exists():
                        live_fallback = str(resolved_test)
                        default_source_local = live_fallback
                    else:
                        if last_test_video["path"] != str(resolved_test):
                            logger.warning(
                                "Test video not found for camera %s: %s (falling back to rtsp)",
                                camera_obj.id,
                                resolved_test,
                            )
                            last_test_video["path"] = str(resolved_test)

                return override_manager.get_camera_source(camera_obj.id, live_fallback)

            if state_local.started_at_utc is None:
                state_local.started_at_utc = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
            live_dir = os.getenv(
                "EDGE_LIVE_ANNOTATED_DIR",
                str(Path(__file__).resolve().parents[3] / "pds-netra-backend" / "data" / "live"),
            )
            live_latest_path = Path(live_dir) / settings.godown_id / f"{camera_obj.id}_latest.jpg"
            live_writer = LiveFrameWriter(str(live_latest_path), latest_interval=0.2)
    
            def _sync_zones() -> None:
                nonlocal last_zone_sync
                now_ts = time.monotonic()
                if now_ts - last_zone_sync < zone_sync_interval:
                    return
                last_zone_sync = now_ts
                url = f"{backend_url}/api/v1/cameras/{camera_obj.id}/zones"
                try:
                    with urllib.request.urlopen(url, timeout=2) as resp:
                        payload = json.loads(resp.read().decode("utf-8"))
                    zones = payload.get("zones", [])
                    if isinstance(zones, list):
                        zone_polygons.clear()
                        for zone in zones:
                            zone_id = zone.get("id")
                            polygon = zone.get("polygon")
                            if not zone_id or not isinstance(polygon, list):
                                continue
                            try:
                                zone_polygons[zone_id] = [tuple(pt) for pt in polygon]
                            except Exception:
                                continue
                except Exception:
                    pass
    
            def snapshotter(img, event_id: str, event_time: datetime.datetime, bbox=None, label=None):
                if snapshot_writer_local is None:
                    return None
                timestamp_utc = event_time.replace(microsecond=0).isoformat().replace('+00:00', 'Z')
                canvas = img
                if bbox:
                    try:
                        import cv2  # type: ignore
                        canvas = img.copy()
                        x1, y1, x2, y2 = bbox
                        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 200, 255), 2)
                        if label:
                            cv2.putText(
                                canvas,
                                str(label),
                                (x1, max(y1 - 6, 10)),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.5,
                                (0, 200, 255),
                                1,
                                cv2.LINE_AA,
                            )
                    except Exception:
                        canvas = img
                return snapshot_writer_local.save(
                    canvas,
                    godown_id=settings.godown_id,
                    camera_id=camera_obj.id,
                    event_id=event_id,
                    timestamp_utc=timestamp_utc,
                )
    
            def bag_handler(objects: list[DetectedObject], now_utc: datetime.datetime, frame=None) -> None:
                if processors_local.bag_processor is None:
                    return
                try:
                    processors_local.bag_processor.process(
                        objects,
                        now_utc,
                        mqtt_client,
                        frame=frame,
                        snapshotter=snapshotter,
                    )
                except Exception as exc:
                    logging.getLogger("camera_loop").exception(
                        "Bag movement processing failed for camera %s: %s", camera_obj.id, exc
                    )
    
            def callback(
                objects: list[DetectedObject],
                frame=None,
            ) -> None:
                """Composite callback handling rule evaluation, ANPR and tamper detection."""
                now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    
                _sync_zones()
    
                if detect_classes_local:
                    objects = [obj for obj in objects if obj.class_name.lower() in detect_classes_local]
    
                # Log per-frame counts for people and face recognition results.
                person_count = sum(1 for obj in objects if obj.class_name == "person")
                known_faces = 0
                unknown_faces = 0
                # Update last frame time and mark camera online
                state_local.last_frame_utc = now
                now_mono = time.monotonic()
                if state_local.last_frame_monotonic is not None:
                    dt = now_mono - state_local.last_frame_monotonic
                    if dt > 0:
                        inst_fps = 1.0 / dt
                        if state_local.fps_estimate is None:
                            state_local.fps_estimate = inst_fps
                        else:
                            state_local.fps_estimate = (state_local.fps_estimate * 0.9) + (inst_fps * 0.1)
                state_local.last_frame_monotonic = now_mono
                if not state_local.is_online:
                    logging.getLogger("camera_loop").info("Camera online: camera=%s", camera_obj.id)
                state_local.is_online = True
                state_local.offline_reported = False
                # Tamper analysis (skip in test mode or when health is disabled)
                if health_enabled_local and frame is not None and current_state["mode"] != "test":
                    try:
                        tamper_candidates = analyze_frame_for_tamper(
                            camera_id=camera_obj.id,
                            frame=frame,
                            now_utc=now,
                            config=health_cfg_local,
                            state=state_local.tamper_state,
                        )
                        # Deduplicate and publish tamper events
                        for cand in tamper_candidates:
                            cooldown_sec = max(1, int(health_cfg_local.cooldown_seconds))
                            last_seen = state_local.last_event_by_reason.get(cand.reason)
                            if last_seen and (now - last_seen).total_seconds() < cooldown_sec:
                                continue
                            severity = "warning"
                            if cand.reason in {"BLACK_FRAME", "SUDDEN_BLACKOUT", "CAMERA_MOVED"}:
                                severity = "critical"
                            image_url = None
                            if cand.snapshot is not None:
                                try:
                                    event_id = str(uuid.uuid4())
                                    image_url = snapshotter(cand.snapshot, event_id, now)
                                except Exception:
                                    image_url = None
                            else:
                                event_id = str(uuid.uuid4())
                            from ..models.event import EventModel, MetaModel  # local import to avoid circular
                            event = EventModel(
                                godown_id=settings.godown_id,
                                camera_id=camera_obj.id,
                                event_id=event_id,
                                event_type=cand.event_type,
                                severity=severity,
                                timestamp_utc=now.replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
                                bbox=None,
                                track_id=None,
                                image_url=image_url,
                                clip_url=None,
                                meta=MetaModel(
                                    zone_id=None,
                                    rule_id="CAM_TAMPER_HEURISTIC",
                                    confidence=cand.confidence,
                                    reason=cand.reason,
                                    extra={k: f"{v:.4f}" for k, v in cand.metrics.items()},
                                ),
                            )
                            mqtt_client.publish_event(event)
                            state_local.last_event_by_reason[cand.reason] = now
                            state_local.last_tamper_reason = cand.reason
                            state_local.last_tamper_time = now
                            logging.getLogger("camera_loop").warning(
                                "Tamper event camera=%s reason=%s severity=%s",
                                camera_obj.id,
                                cand.reason,
                                severity,
                            )
                    except Exception as exc:
                        logging.getLogger("camera_loop").exception(
                            "Tamper analysis failed for camera %s: %s", camera_obj.id, exc
                        )
                # Evaluate detections
                if processors_local.evaluator is not None:
                    try:
                        meta_extra = None
                        if current_state["mode"] == "test" and current_state["run_id"]:
                            meta_extra = {"run_id": str(current_state["run_id"])}
                        processors_local.evaluator.process_detections(
                            objects,
                            now,
                            mqtt_client,
                            frame=frame,
                            snapshotter=snapshotter,
                            instant_only=current_state["mode"] == "test",
                            meta_extra=meta_extra,
                        )
                    except Exception as exc:
                        logging.getLogger("camera_loop").exception(
                            "Rule evaluation failed for camera %s: %s", camera_obj.id, exc
                        )

                if presence_processor_local is not None:
                    try:
                        presence_processor_local.process(
                            objects,
                            now,
                            mqtt_client,
                            frame=frame,
                            snapshotter=snapshotter,
                        )
                    except Exception as exc:
                        logging.getLogger("camera_loop").exception(
                            "After-hours presence processing failed for camera %s: %s", camera_obj.id, exc
                        )

                if fire_processor_local is not None:
                    try:
                        fire_processor_local.process(
                            frame,
                            now,
                            mqtt_client,
                            snapshotter=snapshotter,
                        )
                    except Exception as exc:
                        logging.getLogger("camera_loop").exception(
                            "Fire detection failed for camera %s: %s", camera_obj.id, exc
                        )

                # ANPR + Face + Watchlist
                face_overlays: list[FaceOverlay] = []
                anpr_results: Any = []
                faces: list[tuple[list[int], list[float]]] = []

                if processors_local.anpr_processor is not None and frame is not None:
                    try:
                        anpr_results = processors_local.anpr_processor.process_frame(
                            frame,
                            now,
                            mqtt_client,
                            snapshotter=snapshotter,
                        ) or []
                    except Exception as exc:
                        logging.getLogger("camera_loop").exception(
                            "ANPR processing failed for camera %s: %s", camera_obj.id, exc
                        )
                        anpr_results = []

                if frame is not None and (face_processor_local is not None or watchlist_processor_local is not None):
                    try:
                        faces = detect_faces(frame)
                    except Exception as exc:
                        faces = []
                        logging.getLogger("camera_loop").exception(
                            "Face detection failed for camera %s: %s", camera_obj.id, exc
                        )
                    if watchlist_processor_local is not None:
                        try:
                            watchlist_processor_local.process_faces(
                                faces,
                                now,
                                mqtt_client,
                                snapshotter=snapshotter,
                                frame=frame,
                            )
                        except Exception as exc:
                            logging.getLogger("camera_loop").exception(
                                "Watchlist processing failed for camera %s: %s", camera_obj.id, exc
                            )
                    if face_processor_local is not None:
                        try:
                            face_overlays = face_processor_local.process_faces(faces, now, mqtt_client) or []
                        except Exception as exc:
                            logging.getLogger("camera_loop").exception(
                                "Face recognition failed for camera %s: %s", camera_obj.id, exc
                            )
                            face_overlays = []
                        known_faces = sum(1 for face in face_overlays if face.status == "KNOWN")
                        unknown_faces = sum(1 for face in face_overlays if face.status == "UNKNOWN")

                if os.getenv("EDGE_LOG_FRAME_STATS", "true").lower() in {"1", "true", "yes"}:
                    logging.getLogger("camera_loop").info(
                        "Frame persons=%d faces_known=%d faces_unknown=%d anpr=%d camera=%s mode=%s",
                        person_count,
                        known_faces,
                        unknown_faces,
                        len(anpr_results) if isinstance(anpr_results, list) else 0,
                        camera_obj.id,
                        current_state["mode"],
                    )

                # Visualize
                if frame is not None:
                    dets = [(o.class_name, o.confidence, o.bbox, o.track_id) for o in objects]

                    # ---- IMPORTANT FIX: support BOTH ANPR return formats ----
                    # Some AnprProcessor versions return list of objects with attrs:
                    #   bbox/text/confidence
                    # Others return list of tuples:
                    #   (label, conf, bbox)
                    try:
                        if isinstance(anpr_results, list):
                            for res in anpr_results:
                                if isinstance(res, tuple) and len(res) >= 3:
                                    label = str(res[0])
                                    conf = float(res[1])
                                    bbox = res[2]
                                    if bbox:
                                        dets.append((label, conf, bbox, None))
                                    continue

                                bbox = getattr(res, "bbox", None)
                                text = getattr(res, "text", getattr(res, "plate_text", None))
                                conf = getattr(res, "confidence", 1.0)
                                if bbox and text:
                                    dets.append((f"Plate: {text}", float(conf), bbox, -1))
                    except Exception:
                        pass

                    # Face overlays
                    for face in face_overlays:
                        if face.bbox:
                            label = face.person_name if face.status == "KNOWN" and face.person_name else "Face"
                            dets.append((label, float(face.confidence or 1.0), face.bbox, -1))

                    # Draw zones
                    try:
                        import cv2  # type: ignore
                        for zone_id, polygon in zone_polygons.items():
                            if not polygon:
                                continue
                            pts = [(int(x), int(y)) for x, y in polygon]
                            cv2.polylines(frame, [np.array(pts, dtype=np.int32)], True, (255, 150, 0), 2)
                            label_pt = pts[0]
                            cv2.putText(
                                frame,
                                zone_id,
                                (label_pt[0], max(label_pt[1] - 6, 10)),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.5,
                                (255, 150, 0),
                                1,
                                cv2.LINE_AA,
                            )
                    except Exception:
                        pass
                    if annotated_writer is not None:
                        annotated_writer.write_frame(frame, dets)
                    if live_writer is not None:
                        live_writer.write_frame(frame, dets)
                if (
                    frame is not None
                    and current_state["mode"] == "test"
                    and current_state["run_id"]
                    and objects
                ):
                    now_ts = time.monotonic()
                    if now_ts - current_state["last_snapshot_ts"] >= 0.5:
                        snapshots_root = Path(
                            os.getenv(
                                "EDGE_SNAPSHOT_DIR",
                                str(Path(__file__).resolve().parents[3] / "pds-netra-backend" / "data" / "snapshots"),
                            )
                        )
                        out_dir = snapshots_root / settings.godown_id / current_state["run_id"] / camera_obj.id
                        out_dir.mkdir(parents=True, exist_ok=True)
                        filename = f"det_{int(now_ts * 1000)}.jpg"
                        try:
                            import cv2  # type: ignore
                            canvas = frame.copy()
                            for obj in objects:
                                x1, y1, x2, y2 = obj.bbox
                                cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 200, 255), 2)
                                label = f"{obj.class_name} {obj.confidence:.2f}"
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
                            cv2.imwrite(str(out_dir / filename), canvas)
                        except Exception:
                            pass
                        current_state["last_snapshot_ts"] = now_ts
    
            while True:
                # Handle deactivation
                if not getattr(camera_obj, "is_active", True):
                    if state_local.is_online:
                        logger.info("Camera deactivated: %s", camera_obj.id)
                        state_local.is_online = False
                    time.sleep(5)
                    continue
                current_source, current_mode, current_run_id = _resolve_source_local()
                state_local.suppress_offline_events = not health_enabled_local
                current_state["mode"] = current_mode
                current_state["run_id"] = current_run_id
                if current_mode == "test":
                    # Suppress offline events during test runs
                    state_local.suppress_offline_events = True
                if _is_file_source(current_source):
                    resolved = Path(current_source).expanduser().resolve()
                    if not resolved.exists():
                        logger.warning(
                            "Test video missing for camera %s: %s -> falling back to LIVE RTSP",
                            camera_obj.id,
                            resolved,
                        )
                        # fallback to live
                        current_source = camera_obj.rtsp_url
                        current_mode = "live"
                        current_run_id = None
                    else:
                        current_source = str(resolved)
                logger.info(
                    "Creating pipeline for camera %s (mode=%s, source=%s)",
                    camera_obj.id,
                    current_mode,
                    current_source,
                )
                annotated_writer = None
                if current_mode == "test" and current_run_id:
                    annotated_dir = Path(
                        os.getenv(
                            "EDGE_ANNOTATED_DIR",
                            str(Path(__file__).resolve().parents[3] / "pds-netra-backend" / "data" / "annotated"),
                        )
                    )
                    annotated_path = annotated_dir / settings.godown_id / current_run_id / f"{camera_obj.id}.mp4"
                    latest_path = annotated_dir / settings.godown_id / current_run_id / f"{camera_obj.id}_latest.jpg"
                    annotated_writer = AnnotatedVideoWriter(
                        str(annotated_path),
                        latest_path=str(latest_path),
                        latest_interval=0.2,
                    )
                next_source: dict[str, Optional[str]] = {"value": None}
                next_mode: dict[str, Optional[str]] = {"value": None}
                next_run_id: dict[str, Optional[str]] = {"value": None}
    
                def should_stop() -> bool:
                    if not getattr(camera_obj, "is_active", True):
                        return True
                    desired_source, desired_mode, desired_run_id = _resolve_source_local()
                    if desired_source != current_source:
                        next_source["value"] = desired_source
                        next_mode["value"] = desired_mode
                        next_run_id["value"] = desired_run_id
                        return True
                    return False
    
                pipeline = Pipeline(
                    current_source,
                    camera_obj.id,
                    detector_local,
                    callback,
                    stop_check=should_stop,
                    frame_processors=[bag_handler],
                )
                pipeline.run()
                if annotated_writer is not None:
                    annotated_writer.close()
                    if annotated_writer.frames_written() == 0:
                        logger.warning(
                            "Annotated video has zero frames for camera %s (run_id=%s).",
                            camera_obj.id,
                            current_run_id,
                        )
    
                if next_source["value"]:
                    current_source = next_source["value"]
                    current_mode = next_mode["value"] or "live"
                    current_run_id = next_run_id["value"]
                    continue
                # Handle overrides that arrived while pipeline exited early (e.g., RTSP open failed)
                desired_source, desired_mode, desired_run_id = _resolve_source_local()
                if desired_source != current_source:
                    current_source = desired_source
                    current_mode = desired_mode
                    current_run_id = desired_run_id
                    continue
    
                if current_mode == "test":
                    state_local.suppress_offline_events = True
                    logger.info(
                        "Test run completed for camera %s (run_id=%s)",
                        camera_obj.id,
                        current_run_id,
                    )
                    if current_run_id:
                        try:
                            annotated_dir = Path(
                                os.getenv(
                                    "EDGE_ANNOTATED_DIR",
                                    str(Path(__file__).resolve().parents[3] / "pds-netra-backend" / "data" / "annotated"),
                                )
                            )
                            marker = annotated_dir / settings.godown_id / current_run_id / "completed.json"
                            marker.parent.mkdir(parents=True, exist_ok=True)
                            marker.write_text(
                                json.dumps(
                                    {
                                        "run_id": current_run_id,
                                        "camera_id": camera_obj.id,
                                        "completed_at": datetime.datetime.utcnow().isoformat() + "Z",
                                    },
                                    indent=2,
                                ),
                                encoding="utf-8",
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
    for camera in settings.cameras:
        _start_camera(camera)

    enable_discovery = os.getenv("EDGE_DYNAMIC_CAMERAS", "true").lower() in {"1", "true", "yes"}
    if enable_discovery:
        def _discover_loop() -> None:
            backend_url = os.getenv("EDGE_BACKEND_URL", "http://127.0.0.1:8001").rstrip("/")
            try:
                interval = float(os.getenv("EDGE_CAMERA_DISCOVERY_INTERVAL_SEC", "20"))
            except Exception:
                interval = 20.0
            while True:
                try:
                    url = f"{backend_url}/api/v1/godowns/{settings.godown_id}"
                    with urllib.request.urlopen(url, timeout=3) as resp:
                        payload = json.loads(resp.read().decode("utf-8"))
                    cameras = payload.get("cameras", []) if isinstance(payload, dict) else []
                    for cam in cameras or []:
                        cam_id = cam.get("camera_id")
                        if not cam_id:
                            continue
                        rtsp_url = cam.get("rtsp_url") or cam.get("rtsp")
                        if not rtsp_url:
                            continue
                        zones = []
                        zones_raw = cam.get("zones_json")
                        if zones_raw:
                            try:
                                if isinstance(zones_raw, str):
                                    zones_data = json.loads(zones_raw)
                                else:
                                    zones_data = zones_raw
                                if isinstance(zones_data, list):
                                    for zone in zones_data:
                                        zone_id = zone.get("id") if isinstance(zone, dict) else None
                                        polygon = zone.get("polygon") if isinstance(zone, dict) else None
                                        if zone_id and isinstance(polygon, list):
                                            zones.append(ZoneConfig(id=zone_id, polygon=polygon))
                            except Exception:
                                pass
                        with camera_lock:
                            existing_cam = next((c for c in settings.cameras if c.id == cam_id), None)
                            if existing_cam:
                                # Synchronize existing camera settings
                                existing_cam.rtsp_url = rtsp_url
                                existing_cam.test_video = cam.get("test_video")
                                existing_cam.is_active = cam.get("is_active", True)
                                continue
                            
                            if cam_id in started_cameras:
                                continue
                        role = str(cam.get("role") or "SECURITY").strip().upper()
                        modules_cfg = None
                        modules_raw = cam.get("modules")
                        if isinstance(modules_raw, dict):
                            try:
                                modules_cfg = CameraModules(**modules_raw)
                            except Exception:
                                modules_cfg = None
                        new_camera = CameraConfig(
                            id=cam_id,
                            rtsp_url=rtsp_url,
                            role=role,
                            role_explicit=bool(cam.get("role")),
                            modules=modules_cfg,
                            zones=zones,
                            test_video=cam.get("test_video"),
                            is_active=cam.get("is_active", True)
                        )
                        settings.cameras.append(new_camera)
                        _start_camera(new_camera)
                except Exception:
                    pass
                time.sleep(interval)

        t_discover = threading.Thread(target=_discover_loop, name="CameraDiscovery", daemon=True)
        t_discover.start()

    rules_source = os.getenv("EDGE_RULES_SOURCE", "backend").lower()
    if rules_source == "backend":
        def _apply_rules(updated_rules: list[BaseRule]) -> None:
            for cam_id, bundle in processors.items():
                cam_rules = [r for r in updated_rules if r.camera_id == cam_id]
                cam_cfg = next((c for c in settings.cameras if c.id == cam_id), None)
                modules = select_pipeline(cam_cfg, settings).modules if cam_cfg else None
                if bundle.evaluator is not None and (modules is None or modules.animal_detection_enabled):
                    bundle.evaluator.update_rules(cam_rules)
                elif modules is not None and not modules.animal_detection_enabled:
                    bundle.evaluator = None
                bag_rules = [
                    r for r in cam_rules
                    if isinstance(r, (BagMonitorRule, BagOddHoursRule, BagUnplannedRule, BagTallyMismatchRule))
                ]
                if bag_rules and (modules is None or modules.animal_detection_enabled):
                    if bundle.bag_processor is None:
                        bundle.bag_processor = BagMovementProcessor(
                            camera_id=cam_id,
                            godown_id=settings.godown_id,
                            zone_polygons=bundle.zone_polygons,
                            rules=bag_rules,
                            timezone=settings.timezone,
                            dispatch_plan_path=settings.dispatch_plan_path,
                            dispatch_plan_reload_sec=settings.dispatch_plan_reload_sec,
                            bag_class_keywords=settings.bag_class_keywords,
                            movement_px_threshold=settings.bag_movement_px_threshold,
                            movement_time_window_sec=settings.bag_movement_time_window_sec,
                        )
                    else:
                        bundle.bag_processor.update_rules(bag_rules)
                else:
                    bundle.bag_processor = None

                anpr_rules = [r for r in cam_rules if isinstance(r, (AnprMonitorRule, AnprWhitelistRule, AnprBlacklistRule))]
                if modules is not None and not modules.anpr_enabled:
                    bundle.anpr_processor = None
                elif bundle.anpr_processor is not None:
                    bundle.anpr_processor.update_rules(anpr_rules)

        def _rules_sync_loop() -> None:
            backend_url = os.getenv("EDGE_BACKEND_URL", "http://127.0.0.1:8001")
            try:
                interval = float(os.getenv("EDGE_RULES_SYNC_INTERVAL_SEC", "20"))
            except Exception:
                interval = 20.0
            last_signature = None
            while True:
                try:
                    rule_cfgs = fetch_rule_configs(backend_url, settings.godown_id)
                    if rule_cfgs is None:
                        time.sleep(interval)
                        continue
                    signature = json.dumps([r.__dict__ for r in rule_cfgs], sort_keys=True)
                    if signature != last_signature:
                        with rules_lock:
                            settings.rules = rule_cfgs
                            updated_rules = load_rules(settings)
                        _apply_rules(updated_rules)
                        last_signature = signature
                except Exception:
                    pass
                time.sleep(interval)

        t_rules = threading.Thread(target=_rules_sync_loop, name="RulesSync", daemon=True)
        t_rules.start()

    # Return threads and camera health state mapping
    return threads, camera_states


# The previous dummy callback has been removed in favour of rule-based evaluation
