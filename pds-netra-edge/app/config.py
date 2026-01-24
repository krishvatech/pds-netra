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
class CameraConfig:
    """Configuration for a single camera source."""
    id: str
    rtsp_url: str
    test_video: Optional[str] = None
    zones: List[ZoneConfig] = field(default_factory=list)
    # Health configuration for the camera. If None, defaults will be applied.
    health: Optional['HealthConfig'] = None


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
        raise FileNotFoundError(f"Configuration file {config_path!s} not found")
    with config_path.open('r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


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
    godown_id = os.getenv('GODOWN_ID', data.get('godown_id'))
    timezone = data.get('timezone', 'UTC')
    mqtt_broker_host = os.getenv('MQTT_BROKER_HOST', data.get('mqtt', {}).get('host', 'localhost'))
    mqtt_broker_port = int(os.getenv('MQTT_BROKER_PORT', data.get('mqtt', {}).get('port', 1883)))
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
        cameras_cfg.append(CameraConfig(
            id=cam_id,
            rtsp_url=rtsp_url,
            test_video=cam_dict.get('test_video'),
            zones=zones,
            health=health_cfg,
        ))

    # Load rules
    rules_cfg: List[RuleConfig] = []
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
    )


__all__ = [
    'ZoneConfig',
    'CameraConfig',
    'RuleConfig',
    'Settings',
    'HealthConfig',
    'FaceRecognitionCameraConfig',
    'FaceRecognitionConfig',
    'TrackingConfig',
    'load_settings',
]
