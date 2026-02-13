"""
Configuration loading for the PDS Netra edge node.

This module provides a Settings class that loads configuration data
from a YAML file located on disk and allows overrides via environment
variables. Environment variables take precedence over values defined
in the YAML configuration. See the README for a sample configuration
file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path

import yaml


@dataclass
class ZoneConfig:
    """Definition of a polygonal zone within a camera's field of view."""
    id: str
    polygon: List[List[int]]


@dataclass
class CameraModules:
    """Optional per-camera module overrides."""
    anpr_enabled: Optional[bool] = None
    gate_entry_exit_enabled: Optional[bool] = None
    person_after_hours_enabled: Optional[bool] = None
    animal_detection_enabled: Optional[bool] = None
    fire_detection_enabled: Optional[bool] = None
    health_monitoring_enabled: Optional[bool] = None


@dataclass
class CameraAnprConfig:
    """Per-camera ANPR overrides."""
    gate_line: Optional[List[List[int]]] = None
    inside_side: Optional[str] = None
    direction_inference: Optional[str] = None
    anpr_event_cooldown_seconds: Optional[int] = None


@dataclass
class CameraConfig:
    """Configuration for a single camera source."""
    id: str
    rtsp_url: str
    source_type: str = "live"
    source_path: Optional[str] = None
    source_run_id: Optional[str] = None
    test_video: Optional[str] = None
    role: str = "SECURITY"
    # Track if role was explicitly provided in config to preserve legacy behavior.
    role_explicit: bool = False
    modules: Optional[CameraModules] = None
    anpr: Optional[CameraAnprConfig] = None
    zones: List[ZoneConfig] = field(default_factory=list)
    # Health configuration for the camera. If None, defaults will be applied.
    health: Optional['HealthConfig'] = None
    # Allow dynamic activation/deactivation.
    is_active: bool = True


@dataclass
class RuleConfig:
    """Configuration for a rule that triggers events under certain conditions."""
    id: str
    type: str
    camera_id: str
    zone_id: str
    # Some rules use time-of-day windows specified by start_time/end_time or start/end
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    threshold_seconds: Optional[int] = None
    start_local: Optional[str] = None
    end_local: Optional[str] = None
    cooldown_seconds: Optional[int] = None
    require_active_dispatch_plan: Optional[bool] = None
    allowed_overage_percent: Optional[float] = None
    threshold_distance: Optional[int] = None
    allowed_plates: Optional[List[str]] = None
    blocked_plates: Optional[List[str]] = None


@dataclass
class FaceRecognitionCameraConfig:
    """Per-camera face recognition policy."""
    camera_id: str
    zone_id: str
    allow_unknown: bool = False
    log_known_only: bool = True


@dataclass
class FaceRecognitionConfig:
    """Global face recognition configuration."""
    enabled: bool = False
    known_faces_file: str = "config/known_faces.json"
    min_match_confidence: float = 0.6
    unknown_event_enabled: bool = True
    dedup_interval_seconds: int = 60
    cameras: List[FaceRecognitionCameraConfig] = field(default_factory=list)

@dataclass
class TrackingConfig:
    """Tracking configuration for object IDs."""
    tracker_name: str = "bytetrack.yaml"
    track_persist: bool = True
    conf: Optional[float] = None
    iou: Optional[float] = None


@dataclass
class WatchlistConfig:
    """Watchlist (blacklist) detection configuration."""
    enabled: bool = False
    min_match_confidence: float = 0.6
    cooldown_seconds: int = 120
    sync_interval_sec: int = 300
    auto_embed: bool = True
    http_fallback: bool = False

@dataclass
class AfterHoursPresenceConfig:
    """After-hours presence detection configuration."""
    enabled: bool = False
    day_start: str = "09:00"
    day_end: str = "19:00"
    emit_only_after_hours: bool = True
    person_interval_sec: int = 2
    vehicle_interval_sec: int = 2
    person_cooldown_sec: int = 10
    vehicle_cooldown_sec: int = 10
    min_confidence: float = 0.0
    person_classes: List[str] = field(default_factory=lambda: ["person"])
    vehicle_classes: List[str] = field(default_factory=lambda: ["car", "truck", "bus", "motorcycle", "bicycle", "vehicle"])
    http_fallback: bool = False


@dataclass
class FireDetectionConfig:
    """Fire detection configuration."""
    enabled: bool = False
    model_path: str = "models/fire.pt"
    device: str = "cpu"
    conf: float = 0.35
    iou: float = 0.45
    cooldown_seconds: int = 60
    min_frames_confirm: int = 3
    zones_enabled: bool = False
    interval_sec: float = 1.5
    class_keywords: List[str] = field(default_factory=lambda: ["fire", "smoke"])
    save_snapshot: bool = True

@dataclass
class AnprConfig:
    """Configuration for ANPR/plate recognition."""

    enabled: bool = False
    model_path: str = "models/plate.pt"
    device: str = "cpu"
    conf: float = 0.25
    iou: float = 0.45
    imgsz: int = 640
    max_det: int = 300
    classes: Optional[List[int]] = None
    plate_class_names: Optional[List[str]] = None
    ocr_lang: List[str] = field(default_factory=lambda: ["en"])
    ocr_every_n: int = 1
    ocr_min_conf: float = 0.3
    ocr_debug: bool = False
    validate_india: bool = False
    show_invalid: bool = False
    registered_file: Optional[str] = None
    dedup_interval_sec: int = 30
    save_crops_dir: Optional[str] = None
    save_crops_max: Optional[int] = None
    gate_line: Optional[List[List[int]]] = None
    inside_side: Optional[str] = None
    direction_max_gap_sec: int = 120


@dataclass
class Settings:
    """
    Application settings loaded from YAML and environment variables.

    Parameters are typed for convenience. MQTT parameters may be
    overridden via environment variables using the names specified
    below. Additional fields may be added as the application grows.
    """

    godown_id: str
    timezone: str
    cameras: List[CameraConfig]
    rules: List[RuleConfig]
    mqtt_broker_host: str
    mqtt_broker_port: int
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    face_recognition: Optional[FaceRecognitionConfig] = None
    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    dispatch_plan_path: str = "data/dispatch_plan.json"
    dispatch_plan_reload_sec: int = 10
    bag_class_keywords: List[str] = field(default_factory=list)
    bag_movement_px_threshold: int = 50
    bag_movement_time_window_sec: int = 2
    anpr: Optional[AnprConfig] = None
    watchlist: Optional[WatchlistConfig] = None
    after_hours_presence: Optional[AfterHoursPresenceConfig] = None
    fire_detection: Optional[FireDetectionConfig] = None

# Health configuration for camera monitoring and tamper detection
@dataclass
class HealthConfig:
    """
    Camera health and tamper detection thresholds.

    Attributes
    ----------
    enabled: bool
        Whether health and tamper monitoring is enabled for this camera.
    no_frame_timeout_seconds: int
        Interval in seconds after which a camera without new frames is considered offline.
    min_fps: float
        Minimum expected FPS before health is considered degraded.
    low_light_threshold: float
        Mean brightness below which the scene is considered low light.
    black_frame_threshold: float
        Mean brightness threshold below which a frame is considered black.
    tamper_frame_diff_threshold: float
        Legacy threshold for difference between current frame and baseline for detecting camera movement.
    uniform_std_threshold: float
        Standard deviation threshold below which a frame is considered uniform/blocked.
    blackout_drop_ratio: float
        Sudden drop ratio vs baseline mean for blackout detection.
    blackout_min_baseline: float
        Minimum baseline mean required before using blackout drop ratio.
    moved_diff_threshold: float
        Normalized diff threshold (0..1) for camera moved detection.
    blur_threshold: float
        Laplacian variance threshold below which a frame is considered blurred.
    snapshot_on_tamper: bool
        Whether to capture a snapshot when a tamper event is detected.
    low_light_consecutive_frames: int
        Number of consecutive low-light frames required before emitting a low-light event.
    blocked_stddev_threshold: float
        Legacy uniform frame stddev threshold retained for backward compatibility.
    blocked_consecutive_frames: int
        Number of consecutive uniform frames required before emitting a lens blocked event.
    blur_consecutive_frames: int
        Number of consecutive blurred frames required before emitting a blur event.
    moved_consecutive_frames: int
        Number of consecutive frames with high difference required before emitting a camera moved event.
    cooldown_seconds: int
        Per-reason cooldown window before emitting the same tamper event again.
    clear_consecutive_frames: int
        Number of normal frames required before clearing a tamper condition.
    """

    enabled: bool = True
    no_frame_timeout_seconds: int = 15
    min_fps: float = 3.0
    low_light_threshold: float = 25.0
    black_frame_threshold: float = 5.0
    tamper_frame_diff_threshold: float = 0.8
    uniform_std_threshold: float = 6.0
    blackout_drop_ratio: float = 0.55
    blackout_min_baseline: float = 25.0
    moved_diff_threshold: float = 0.35
    blur_threshold: float = 50.0
    snapshot_on_tamper: bool = True
    low_light_consecutive_frames: int = 30
    blocked_stddev_threshold: float = 10.0
    blocked_consecutive_frames: int = 5
    blur_consecutive_frames: int = 5
    moved_consecutive_frames: int = 1
    cooldown_seconds: int = 60
    clear_consecutive_frames: int = 15


def _load_yaml_file(config_path: Path) -> dict:
    """Load a YAML configuration file and return a dictionary."""
    if not config_path.exists():
        allow_missing = os.getenv("EDGE_ALLOW_MISSING_CONFIG", "false").lower() in {"1", "true", "yes"}
        if allow_missing:
            return {}
        raise FileNotFoundError(f"Configuration file {config_path!s} not found")
    with config_path.open('r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def _parse_optional_bool(value: object) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return None


def _parse_gate_line(value: object) -> Optional[List[List[int]]]:
    if not value:
        return None
    if isinstance(value, dict):
        x1 = value.get("x1")
        y1 = value.get("y1")
        x2 = value.get("x2")
        y2 = value.get("y2")
        try:
            if None not in (x1, y1, x2, y2):
                return [[int(x1), int(y1)], [int(x2), int(y2)]]
        except Exception:
            return None
        return None
    if isinstance(value, list) and len(value) == 2:
        try:
            p1, p2 = value
            if (
                isinstance(p1, list)
                and isinstance(p2, list)
                and len(p1) == 2
                and len(p2) == 2
            ):
                return [[int(p1[0]), int(p1[1])], [int(p2[0]), int(p2[1])]]
        except Exception:
            return None
    return None


def _parse_camera_modules(value: object) -> Optional[CameraModules]:
    if not isinstance(value, dict):
        return None
    modules = CameraModules(
        anpr_enabled=_parse_optional_bool(value.get("anpr_enabled")),
        gate_entry_exit_enabled=_parse_optional_bool(value.get("gate_entry_exit_enabled")),
        person_after_hours_enabled=_parse_optional_bool(value.get("person_after_hours_enabled")),
        animal_detection_enabled=_parse_optional_bool(value.get("animal_detection_enabled")),
        fire_detection_enabled=_parse_optional_bool(value.get("fire_detection_enabled")),
        health_monitoring_enabled=_parse_optional_bool(value.get("health_monitoring_enabled")),
    )
    if all(getattr(modules, field) is None for field in modules.__dataclass_fields__):
        return None
    return modules


def _parse_camera_anpr_config(cam_dict: dict) -> Optional[CameraAnprConfig]:
    data = cam_dict.get("anpr") or {}
    if not isinstance(data, dict):
        data = {}
    gate_line = _parse_gate_line(data.get("gate_line") or cam_dict.get("gate_line"))
    inside_side = data.get("inside_side") or cam_dict.get("inside_side")
    direction_inference = data.get("direction_inference") or cam_dict.get("direction_inference")
    if isinstance(direction_inference, str):
        direction_inference = direction_inference.strip().upper()
    cooldown = data.get("anpr_event_cooldown_seconds") or cam_dict.get("anpr_event_cooldown_seconds")
    try:
        cooldown_val = int(cooldown) if cooldown is not None else None
    except Exception:
        cooldown_val = None
    if gate_line is None and inside_side is None and direction_inference is None and cooldown_val is None:
        return None
    return CameraAnprConfig(
        gate_line=gate_line,
        inside_side=str(inside_side).strip().upper() if inside_side else None,
        direction_inference=direction_inference,
        anpr_event_cooldown_seconds=cooldown_val,
    )


def load_settings(config_path: str) -> Settings:
    """
    Load settings from a YAML file and environment variables.

    Environment variable overrides:

    - ``GODOWN_ID`` overrides ``godown_id``
    - ``MQTT_BROKER_HOST`` overrides broker host (defaults to ``localhost``)
    - ``MQTT_BROKER_PORT`` overrides broker port (defaults to 1883)
    - ``MQTT_USERNAME`` provides MQTT username if set
    - ``MQTT_PASSWORD`` provides MQTT password if set

    Parameters
    ----------
    config_path: str
        Path to the YAML configuration file.

    Returns
    -------
    Settings
        A Settings instance with configuration and environment overrides applied.
    """
    path = Path(config_path)
    data = _load_yaml_file(path)

    # Apply environment variable overrides
    godown_id = os.getenv("GODOWN_ID", data.get("godown_id"))
    timezone = os.getenv("EDGE_TIMEZONE", data.get("timezone", "UTC"))

    if not godown_id:
        raise ValueError("Missing GODOWN_ID. Set GODOWN_ID in .env or set godown_id in YAML.")

    mqtt_broker_host = os.getenv(
        "MQTT_BROKER_HOST",
        os.getenv("MQTT_HOST", data.get("mqtt", {}).get("host", "localhost")),
    )
    mqtt_broker_port = int(
        os.getenv("MQTT_BROKER_PORT", os.getenv("MQTT_PORT", data.get("mqtt", {}).get("port", 1883)))
    )
    mqtt_username = os.getenv('MQTT_USERNAME', data.get('mqtt', {}).get('username'))
    mqtt_password = os.getenv('MQTT_PASSWORD', data.get('mqtt', {}).get('password'))
    dispatch_plan_path = os.getenv(
        "EDGE_DISPATCH_PLAN_PATH",
        str(Path(data.get("dispatch_plan_path", "data/dispatch_plan.json")).expanduser()),
    )
    try:
        dispatch_plan_reload_sec = int(os.getenv("EDGE_DISPATCH_PLAN_RELOAD_SEC", data.get("dispatch_plan_reload_sec", 10)))
    except Exception:
        dispatch_plan_reload_sec = 10
    bag_keywords_raw = os.getenv("EDGE_BAG_CLASS_KEYWORDS", "")
    if not bag_keywords_raw:
        bag_keywords_raw = ",".join(data.get("bag_class_keywords", []) or [])
    bag_class_keywords = [kw.strip().lower() for kw in bag_keywords_raw.split(",") if kw.strip()]
    if not bag_class_keywords:
        bag_class_keywords = ["bag", "sack", "backpack", "grain_sack"]
    try:
        bag_movement_px_threshold = int(os.getenv("EDGE_BAG_MOVE_PX", data.get("bag_movement_px_threshold", 50)))
    except Exception:
        bag_movement_px_threshold = 50
    try:
        bag_movement_time_window_sec = int(os.getenv("EDGE_BAG_MOVE_TIME_SEC", data.get("bag_movement_time_window_sec", 2)))
    except Exception:
        bag_movement_time_window_sec = 2

    tracking_data = data.get("tracking") or {}
    try:
        tracking_cfg = TrackingConfig(
            tracker_name=str(tracking_data.get("tracker_name", "bytetrack.yaml")),
            track_persist=bool(tracking_data.get("track_persist", True)),
            conf=float(tracking_data["conf"]) if "conf" in tracking_data else None,
            iou=float(tracking_data["iou"]) if "iou" in tracking_data else None,
        )
    except Exception:
        tracking_cfg = TrackingConfig()

    # Load cameras
    cameras_cfg: List[CameraConfig] = []
    for cam_dict in data.get('cameras', []):
        zones = [ZoneConfig(**zone) for zone in cam_dict.get('zones', [])]
        # Parse health config if provided
        health_cfg_dict = cam_dict.get('health') or {}
        health_cfg = None
        try:
            # If health section exists and is a dict, instantiate HealthConfig
            if isinstance(health_cfg_dict, dict) and health_cfg_dict:
                health_cfg = HealthConfig(**health_cfg_dict)
        except Exception:
            # Leave health_cfg as None if parsing fails
            health_cfg = None
        cam_id = cam_dict['id']
        rtsp_env_key = f"RTSP_URL_{cam_id}"
        rtsp_url = os.getenv(rtsp_env_key, cam_dict['rtsp_url'])
        role_raw = cam_dict.get("role")
        role_explicit = "role" in cam_dict and role_raw is not None
        role = str(role_raw or "SECURITY").strip().upper()
        modules_cfg = _parse_camera_modules(cam_dict.get("modules"))
        anpr_cam_cfg = _parse_camera_anpr_config(cam_dict)
        source_type = str(cam_dict.get("source_type") or "live").strip().lower()
        if source_type not in {"live", "test"}:
            source_type = "live"
        cameras_cfg.append(CameraConfig(
            id=cam_id,
            rtsp_url=rtsp_url,
            source_type=source_type,
            source_path=cam_dict.get("source_path"),
            source_run_id=cam_dict.get("source_run_id"),
            test_video=cam_dict.get('test_video'),
            role=role,
            role_explicit=role_explicit,
            modules=modules_cfg,
            anpr=anpr_cam_cfg,
            zones=zones,
            health=health_cfg,
            is_active=bool(cam_dict.get("is_active", True)),
        ))

    # Load rules (YAML deprecated by default; use EDGE_RULES_SOURCE=yaml to enable)
    rules_cfg: List[RuleConfig] = []
    rules_source = os.getenv("EDGE_RULES_SOURCE", "backend").lower()
    if rules_source != "backend":
        for rule in data.get('rules', []):
            rules_cfg.append(RuleConfig(**rule))

    # Load face recognition config if present
    face_recognition_cfg: Optional[FaceRecognitionConfig] = None
    fr_data = data.get("face_recognition")
    if isinstance(fr_data, dict):
        fr_cameras: List[FaceRecognitionCameraConfig] = []
        for cam in fr_data.get("cameras", []) or []:
            try:
                fr_cameras.append(FaceRecognitionCameraConfig(**cam))
            except Exception:
                continue
        try:
            face_recognition_cfg = FaceRecognitionConfig(
                enabled=bool(fr_data.get("enabled", False)),
                known_faces_file=str(fr_data.get("known_faces_file", "config/known_faces.json")),
                min_match_confidence=float(fr_data.get("min_match_confidence", 0.6)),
                unknown_event_enabled=bool(fr_data.get("unknown_event_enabled", True)),
                dedup_interval_seconds=int(fr_data.get("dedup_interval_seconds", 60)),
                cameras=fr_cameras,
            )
        except Exception:
            face_recognition_cfg = None

    # Load ANPR config if present
    anpr_cfg: Optional[AnprConfig] = None
    anpr_data = data.get("anpr")
    if isinstance(anpr_data, dict):
        try:
            classes = anpr_data.get("classes")
            if classes is not None:
                classes = [int(x) for x in classes]
            plate_class_names = anpr_data.get("plate_class_names")
            if plate_class_names is not None:
                plate_class_names = [str(x) for x in plate_class_names]
            ocr_lang = anpr_data.get("ocr_lang")
            if ocr_lang is not None:
                ocr_lang = [str(x) for x in ocr_lang]


            anpr_cfg = AnprConfig(
                enabled=bool(anpr_data.get("enabled", False)),
                model_path=str(anpr_data.get("model_path", "./ML_MOdel/anpr.pt")),
                device=str(anpr_data.get("device", "cpu")),
                conf=float(anpr_data.get("conf", 0.25)),
                iou=float(anpr_data.get("iou", 0.45)),
                imgsz=int(anpr_data.get("imgsz", 640)),
                max_det=int(anpr_data.get("max_det", 300)),
                classes=classes,
                plate_class_names=plate_class_names,
                ocr_lang=ocr_lang or ["en"],
                ocr_every_n=int(anpr_data.get("ocr_every_n", 1)),
                ocr_min_conf=float(anpr_data.get("ocr_min_conf", 0.3)),
                ocr_debug=bool(anpr_data.get("ocr_debug", False)),
                validate_india=bool(anpr_data.get("validate_india", False)),
                show_invalid=bool(anpr_data.get("show_invalid", False)),
                registered_file=anpr_data.get("registered_file"),
                dedup_interval_sec=int(anpr_data.get("dedup_interval_sec", 30)),
                save_crops_dir=anpr_data.get("save_crops_dir"),
                save_crops_max=anpr_data.get("save_crops_max"),
                gate_line=anpr_data.get("gate_line"),
                inside_side=anpr_data.get("inside_side"),
                direction_max_gap_sec=int(anpr_data.get("direction_max_gap_sec", 120)),
            )
        except Exception:
            anpr_cfg = None

    watchlist_cfg = _load_watchlist_config(data)
    after_hours_cfg = _load_after_hours_presence_config(data)
    fire_cfg = _load_fire_detection_config(data)

    return Settings(
        godown_id=godown_id,
        timezone=timezone,
        cameras=cameras_cfg,
        rules=rules_cfg,
        mqtt_broker_host=mqtt_broker_host,
        mqtt_broker_port=mqtt_broker_port,
        mqtt_username=mqtt_username,
        mqtt_password=mqtt_password,
        face_recognition=face_recognition_cfg,
        tracking=tracking_cfg,
        dispatch_plan_path=dispatch_plan_path,
        dispatch_plan_reload_sec=dispatch_plan_reload_sec,
        bag_class_keywords=bag_class_keywords,
        bag_movement_px_threshold=bag_movement_px_threshold,
        bag_movement_time_window_sec=bag_movement_time_window_sec,
        anpr=anpr_cfg,
        watchlist=watchlist_cfg,
        after_hours_presence=after_hours_cfg,
        fire_detection=fire_cfg,
    )


def _load_watchlist_config(data: dict) -> WatchlistConfig:
    wl_data = data.get("watchlist") or {}
    enabled = os.getenv("EDGE_WATCHLIST_ENABLED", str(wl_data.get("enabled", False))).lower() in {"1", "true", "yes"}
    try:
        min_conf = float(os.getenv("EDGE_WATCHLIST_MIN_CONF", wl_data.get("min_match_confidence", 0.6)))
    except Exception:
        min_conf = 0.6
    try:
        cooldown = int(os.getenv("EDGE_WATCHLIST_COOLDOWN_SEC", wl_data.get("cooldown_seconds", 120)))
    except Exception:
        cooldown = 120
    try:
        sync_sec = int(os.getenv("EDGE_WATCHLIST_SYNC_SEC", wl_data.get("sync_interval_sec", 300)))
    except Exception:
        sync_sec = 300
    auto_embed = os.getenv("EDGE_WATCHLIST_AUTO_EMBED", str(wl_data.get("auto_embed", True))).lower() in {"1", "true", "yes"}
    http_fallback = os.getenv("EDGE_WATCHLIST_HTTP_FALLBACK", str(wl_data.get("http_fallback", False))).lower() in {"1", "true", "yes"}
    return WatchlistConfig(
        enabled=enabled,
        min_match_confidence=min_conf,
        cooldown_seconds=cooldown,
        sync_interval_sec=sync_sec,
        auto_embed=auto_embed,
        http_fallback=http_fallback,
    )


def _load_after_hours_presence_config(data: dict) -> AfterHoursPresenceConfig:
    ah_data = data.get("after_hours_presence") or {}
    enabled = os.getenv("EDGE_AFTER_HOURS_ENABLED", str(ah_data.get("enabled", False))).lower() in {"1", "true", "yes"}
    day_start = os.getenv("EDGE_AFTER_HOURS_DAY_START", ah_data.get("day_start", "09:00"))
    day_end = os.getenv("EDGE_AFTER_HOURS_DAY_END", ah_data.get("day_end", "19:00"))
    emit_only = os.getenv("EDGE_AFTER_HOURS_ONLY", str(ah_data.get("emit_only_after_hours", True))).lower() in {"1", "true", "yes"}
    try:
        person_interval = int(os.getenv("EDGE_AFTER_HOURS_PERSON_INTERVAL_SEC", ah_data.get("person_interval_sec", 2)))
    except Exception:
        person_interval = 2
    try:
        vehicle_interval = int(os.getenv("EDGE_AFTER_HOURS_VEHICLE_INTERVAL_SEC", ah_data.get("vehicle_interval_sec", 2)))
    except Exception:
        vehicle_interval = 2
    try:
        person_cooldown = int(os.getenv("EDGE_AFTER_HOURS_PERSON_COOLDOWN_SEC", ah_data.get("person_cooldown_sec", 10)))
    except Exception:
        person_cooldown = 10
    try:
        vehicle_cooldown = int(os.getenv("EDGE_AFTER_HOURS_VEHICLE_COOLDOWN_SEC", ah_data.get("vehicle_cooldown_sec", 10)))
    except Exception:
        vehicle_cooldown = 10
    try:
        min_conf = float(os.getenv("EDGE_AFTER_HOURS_MIN_CONF", ah_data.get("min_confidence", 0.0)))
    except Exception:
        min_conf = 0.0
    person_classes_raw = os.getenv("EDGE_AFTER_HOURS_PERSON_CLASSES") or ah_data.get("person_classes") or ["person"]
    vehicle_classes_raw = os.getenv("EDGE_AFTER_HOURS_VEHICLE_CLASSES") or ah_data.get("vehicle_classes") or [
        "car",
        "truck",
        "bus",
        "motorcycle",
        "bicycle",
        "vehicle",
    ]
    if isinstance(person_classes_raw, str):
        person_classes = [c.strip() for c in person_classes_raw.split(",") if c.strip()]
    else:
        person_classes = [str(c) for c in person_classes_raw]
    if isinstance(vehicle_classes_raw, str):
        vehicle_classes = [c.strip() for c in vehicle_classes_raw.split(",") if c.strip()]
    else:
        vehicle_classes = [str(c) for c in vehicle_classes_raw]
    http_fallback = os.getenv("EDGE_AFTER_HOURS_HTTP_FALLBACK", str(ah_data.get("http_fallback", False))).lower() in {"1", "true", "yes"}
    return AfterHoursPresenceConfig(
        enabled=enabled,
        day_start=str(day_start),
        day_end=str(day_end),
        emit_only_after_hours=emit_only,
        person_interval_sec=person_interval,
        vehicle_interval_sec=vehicle_interval,
        person_cooldown_sec=person_cooldown,
        vehicle_cooldown_sec=vehicle_cooldown,
        min_confidence=min_conf,
        person_classes=person_classes,
        vehicle_classes=vehicle_classes,
        http_fallback=http_fallback,
    )


def _load_fire_detection_config(data: dict) -> FireDetectionConfig:
    fd_data = data.get("fire_detection") or {}
    enabled = os.getenv("EDGE_FIRE_ENABLED", str(fd_data.get("enabled", False))).lower() in {"1", "true", "yes"}
    model_path = os.getenv("EDGE_FIRE_MODEL_PATH", fd_data.get("model_path", "models/fire.pt"))
    device = os.getenv("EDGE_FIRE_DEVICE", fd_data.get("device", "cpu"))
    try:
        conf = float(os.getenv("EDGE_FIRE_CONF", fd_data.get("conf", 0.35)))
    except Exception:
        conf = 0.35
    try:
        iou = float(os.getenv("EDGE_FIRE_IOU", fd_data.get("iou", 0.45)))
    except Exception:
        iou = 0.45
    try:
        cooldown = int(os.getenv("EDGE_FIRE_COOLDOWN_SEC", fd_data.get("cooldown_seconds", 60)))
    except Exception:
        cooldown = 60
    try:
        min_frames = int(os.getenv("EDGE_FIRE_MIN_FRAMES", fd_data.get("min_frames_confirm", 3)))
    except Exception:
        min_frames = 3
    zones_enabled = os.getenv("EDGE_FIRE_ZONES_ENABLED", str(fd_data.get("zones_enabled", False))).lower() in {"1", "true", "yes"}
    try:
        interval_sec = float(os.getenv("EDGE_FIRE_INTERVAL_SEC", fd_data.get("interval_sec", 1.5)))
    except Exception:
        interval_sec = 1.5
    class_keywords_raw = os.getenv("EDGE_FIRE_CLASS_KEYWORDS") or fd_data.get("class_keywords") or ["fire", "smoke"]
    if isinstance(class_keywords_raw, str):
        class_keywords = [c.strip() for c in class_keywords_raw.split(",") if c.strip()]
    else:
        class_keywords = [str(c) for c in class_keywords_raw]
    save_snapshot = os.getenv("EDGE_FIRE_SAVE_SNAPSHOT", str(fd_data.get("save_snapshot", True))).lower() in {"1", "true", "yes"}
    return FireDetectionConfig(
        enabled=enabled,
        model_path=str(model_path),
        device=str(device),
        conf=conf,
        iou=iou,
        cooldown_seconds=cooldown,
        min_frames_confirm=min_frames,
        zones_enabled=zones_enabled,
        interval_sec=interval_sec,
        class_keywords=class_keywords,
        save_snapshot=save_snapshot,
    )


__all__ = [
    'ZoneConfig',
    'CameraModules',
    'CameraAnprConfig',
    'CameraConfig',
    'RuleConfig',
    'Settings',
    'HealthConfig',
    'FaceRecognitionCameraConfig',
    'FaceRecognitionConfig',
    'TrackingConfig',
    'AnprConfig',
    'WatchlistConfig',
    'AfterHoursPresenceConfig',
    'FireDetectionConfig',
    'load_settings',
]
