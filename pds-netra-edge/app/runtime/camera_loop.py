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
from pathlib import Path

from ..cv.pipeline import Pipeline, DetectedObject
from ..cv.yolo_detector import YoloDetector
from ..cv.tracker import SimpleTracker
from ..events.mqtt_client import MQTTClient
from ..rules.loader import load_rules, AnprMonitorRule, AnprWhitelistRule, AnprBlacklistRule
from ..rules.evaluator import RulesEvaluator
from ..cv.anpr import AnprProcessor, PlateDetector
from ..cv.tamper import analyze_frame_for_tamper, CameraTamperState, TamperEventCandidate
import datetime
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple
from ..config import Settings, HealthConfig, FaceRecognitionCameraConfig
from ..cv.face_id import FaceRecognitionProcessor, load_known_faces
from ..overrides import EdgeOverrideManager
from ..snapshots import default_snapshot_writer


@dataclass
class CameraHealthState:
    """Mutable state for camera health and tamper monitoring."""

    # Last UTC time when a frame was successfully processed
    last_frame_utc: Optional[datetime.datetime] = None
    # Flag indicating whether the camera is currently considered online
    is_online: bool = False
    # Last tamper reason emitted (e.g., "LOW_LIGHT", "LENS_BLOCKED").
    last_tamper_reason: Optional[str] = None
    # Time when the last tamper event was emitted
    last_tamper_time: Optional[datetime.datetime] = None
    # Underlying state used by tamper analysis heuristics
    tamper_state: CameraTamperState = field(default_factory=CameraTamperState)
    # Suppress offline events after test run completion
    suppress_offline_events: bool = False


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
    override_path = os.getenv("EDGE_OVERRIDE_PATH")
    override_manager = EdgeOverrideManager(override_path, refresh_interval=5)
    if override_path:
        logger.info("Edge override path: %s", override_path)
    # Load all rules once and convert into typed objects
    all_rules = load_rules(settings)
    for camera in settings.cameras:
        default_source = camera.rtsp_url
        if camera.test_video:
            test_path = Path(camera.test_video).expanduser()
            if test_path.is_absolute():
                resolved_test = test_path
            else:
                resolved_test = (Path.cwd() / test_path).resolve()
            if resolved_test.exists():
                # Use test video if provided and available
                default_source = str(resolved_test)
            else:
                logger.warning(
                    "Test video not found for camera %s: %s (falling back to rtsp)",
                    camera.id,
                    resolved_test,
                )
        try:
            detector = YoloDetector(device=device)
        except Exception as exc:
            logger.error("Error loading YOLO detector: %s", exc)
            continue
        tracker = SimpleTracker()
        # Prepare rules and zone polygons for this camera
        camera_rules = [r for r in all_rules if r.camera_id == camera.id]
        zone_polygons: dict[str, list[tuple[int, int]]] = {}
        for zone in camera.zones:
            # Convert lists to tuples for point-in-polygon checks
            zone_polygons[zone.id] = [tuple(pt) for pt in zone.polygon]
        evaluator = RulesEvaluator(
            camera_id=camera.id,
            godown_id=settings.godown_id,
            rules=camera_rules,
            zone_polygons=zone_polygons,
            timezone=settings.timezone,
        )
        # Determine if ANPR rules apply for this camera
        anpr_rules = [r for r in camera_rules if isinstance(r, (AnprMonitorRule, AnprWhitelistRule, AnprBlacklistRule))]
        anpr_processor: Optional[AnprProcessor] = None
        if anpr_rules:
            try:
                plate_detector = PlateDetector(detector)
                anpr_processor = AnprProcessor(
                    camera_id=camera.id,
                    godown_id=settings.godown_id,
                    rules=anpr_rules,
                    zone_polygons=zone_polygons,
                    timezone=settings.timezone,
                    plate_detector=plate_detector,
                    ocr_engine=None,
                    dedup_interval_sec=30,
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

        face_processor: Optional[FaceRecognitionProcessor] = None
        fr_cfg = settings.face_recognition
        if fr_cfg is not None and fr_cfg.enabled:
            fr_cam_cfg: Optional[FaceRecognitionCameraConfig] = None
            for cam_cfg in fr_cfg.cameras:
                if cam_cfg.camera_id == camera.id:
                    fr_cam_cfg = cam_cfg
                    break
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

        snapshot_writer = default_snapshot_writer()

        def _is_file_source(source_val: str) -> bool:
            return not (
                source_val.startswith("rtsp://")
                or source_val.startswith("http://")
                or source_val.startswith("https://")
            )

        def camera_runner(
            camera_obj,
            default_source_local: str,
            evaluator_local: RulesEvaluator,
            anpr_processor_local: Optional[AnprProcessor],
            face_processor_local: Optional[FaceRecognitionProcessor],
            health_cfg_local: HealthConfig,
            state_local: CameraHealthState,
            detector_local: YoloDetector,
            tracker_local: SimpleTracker,
            snapshot_writer_local,
        ) -> None:
            def callback(
                objects: list[DetectedObject],
                frame=None,
            ) -> None:
                """Composite callback handling rule evaluation, ANPR and tamper detection."""
                now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
                # Update last frame time and mark camera online
                state_local.last_frame_utc = now
                state_local.is_online = True
                # Perform tamper analysis if a frame is available
                if frame is not None:
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
                            # Determine cooldown: avoid emitting repeated events of same type too often
                            cooldown_sec = 30
                            should_emit = False
                            if state_local.last_tamper_reason != cand.reason:
                                should_emit = True
                            else:
                                # If same reason, ensure cooldown expired
                                if state_local.last_tamper_time is None:
                                    should_emit = True
                                else:
                                    elapsed = (now - state_local.last_tamper_time).total_seconds()
                                    if elapsed > cooldown_sec:
                                        should_emit = True
                            if should_emit:
                                # Determine event_type and severity
                                if cand.reason == "LOW_LIGHT":
                                    event_type = "LOW_LIGHT"
                                else:
                                    event_type = "CAMERA_TAMPERED"
                                severity = "warning"
                                # Construct event model
                                from ..models.event import EventModel, MetaModel  # local import to avoid circular
                                event = EventModel(
                                    godown_id=settings.godown_id,
                                    camera_id=camera_obj.id,
                                    event_id=str(uuid.uuid4()),
                                    event_type=event_type,
                                    severity=severity,
                                    timestamp_utc=now.replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
                                    bbox=[],  # tamper events do not include bounding boxes
                                    track_id=-1,
                                    image_url=None,
                                    clip_url=None,
                                    meta=MetaModel(
                                        zone_id="",  # zone not applicable
                                        rule_id="CAM_TAMPER_HEURISTIC",
                                        confidence=cand.confidence,
                                        reason=cand.reason,
                                        extra={},
                                    ),
                                )
                                mqtt_client.publish_event(event)
                                # Update state
                                state_local.last_tamper_reason = cand.reason
                                state_local.last_tamper_time = now
                    except Exception as exc:
                        logging.getLogger("camera_loop").exception(
                            "Tamper analysis failed for camera %s: %s", camera_obj.id, exc
                        )
                # Evaluate detections for this camera using the shared evaluator
                try:
                    def snapshotter(img, event_id: str, event_time: datetime.datetime):
                        if snapshot_writer_local is None:
                            return None
                        timestamp_utc = event_time.replace(microsecond=0).isoformat().replace('+00:00', 'Z')
                        return snapshot_writer_local.save(
                            img,
                            godown_id=settings.godown_id,
                            camera_id=camera_obj.id,
                            event_id=event_id,
                            timestamp_utc=timestamp_utc,
                        )

                    evaluator_local.process_detections(
                        objects,
                        now,
                        mqtt_client,
                        frame=frame,
                        snapshotter=snapshotter,
                    )
                except Exception as exc:
                    logging.getLogger("camera_loop").exception(
                        "Rule evaluation failed for camera %s: %s", camera_obj.id, exc
                    )
                # Process ANPR if applicable and a frame is provided
                if anpr_processor_local is not None and frame is not None:
                    try:
                        anpr_processor_local.process_frame(frame, now, mqtt_client)
                    except Exception as exc:
                        logging.getLogger("camera_loop").exception(
                            "ANPR processing failed for camera %s: %s", camera_obj.id, exc
                        )
                if face_processor_local is not None and frame is not None:
                    face_processor_local.process_frame(frame, now, mqtt_client)

            def _resolve_source_local() -> tuple[str, str, Optional[str]]:
                return override_manager.get_camera_source(camera_obj.id, default_source_local)

            current_source, current_mode, current_run_id = _resolve_source_local()
            while True:
                state_local.suppress_offline_events = False
                if _is_file_source(current_source):
                    resolved = Path(current_source).expanduser().resolve()
                    if not resolved.exists():
                        logger.error(
                            "Video source not found for camera %s: %s",
                            camera_obj.id,
                            resolved,
                        )
                        break
                    current_source = str(resolved)
                logger.info(
                    "Creating pipeline for camera %s (mode=%s, source=%s)",
                    camera_obj.id,
                    current_mode,
                    current_source,
                )
                next_source: dict[str, Optional[str]] = {"value": None}
                next_mode: dict[str, Optional[str]] = {"value": None}
                next_run_id: dict[str, Optional[str]] = {"value": None}

                def should_stop() -> bool:
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
                    tracker_local,
                    callback,
                    stop_check=should_stop,
                )
                pipeline.run()

                if next_source["value"]:
                    current_source = next_source["value"]
                    current_mode = next_mode["value"] or "live"
                    current_run_id = next_run_id["value"]
                    continue

                if current_mode == "test":
                    state_local.suppress_offline_events = True
                    logger.info(
                        "Test run completed for camera %s (run_id=%s)",
                        camera_obj.id,
                        current_run_id,
                    )
                break

        t = threading.Thread(
            target=camera_runner,
            args=(
                camera,
                default_source,
                evaluator,
                anpr_processor,
                face_processor,
                health_cfg,
                state,
                detector,
                tracker,
                snapshot_writer,
            ),
            name=f"Pipeline-{camera.id}",
            daemon=True,
        )
        t.start()
        threads.append(t)
    # Return threads and camera health state mapping
    return threads, camera_states


# The previous dummy callback has been removed in favour of rule-based evaluation
