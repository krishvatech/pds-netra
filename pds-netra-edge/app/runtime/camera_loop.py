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
import time
import json

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
from ..annotated_video import AnnotatedVideoWriter, LiveFrameWriter


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
            model_path = os.getenv("EDGE_YOLO_MODEL", "best.pt")
            detector = YoloDetector(model_name=model_path, device=device)
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
        try:
            alert_min_conf = float(os.getenv("EDGE_ALERT_MIN_CONF", "0.5"))
        except ValueError:
            alert_min_conf = 0.5
        evaluator = RulesEvaluator(
            camera_id=camera.id,
            godown_id=settings.godown_id,
            rules=camera_rules,
            zone_polygons=zone_polygons,
            timezone=settings.timezone,
            alert_on_person=os.getenv("EDGE_ALERT_ON_PERSON", "false").lower() in {"1", "true", "yes"},
            person_alert_cooldown_sec=int(os.getenv("EDGE_ALERT_PERSON_COOLDOWN", "10")),
            alert_classes=[
                c.strip()
                for c in os.getenv("EDGE_ALERT_ON_CLASSES", "").split(",")
                if c.strip()
            ],
            alert_severity=os.getenv("EDGE_ALERT_SEVERITY", "warning"),
            alert_min_conf=alert_min_conf,
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
            annotated_writer: Optional[AnnotatedVideoWriter] = None
            live_writer: Optional[LiveFrameWriter] = None
            current_state = {"mode": "live", "run_id": None, "last_snapshot_ts": 0.0}
            live_dir = os.getenv(
                "EDGE_LIVE_ANNOTATED_DIR",
                str(Path(__file__).resolve().parents[3] / "pds-netra-backend" / "data" / "live"),
            )
            live_latest_path = Path(live_dir) / settings.godown_id / f"{camera_obj.id}_latest.jpg"
            live_writer = LiveFrameWriter(str(live_latest_path), latest_interval=0.2)
            def callback(
                objects: list[DetectedObject],
                frame=None,
            ) -> None:
                """Composite callback handling rule evaluation, ANPR and tamper detection."""
                now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
                # Update last frame time and mark camera online
                state_local.last_frame_utc = now
                state_local.is_online = True
                # Perform tamper analysis if a frame is available (skip in test mode)
                if frame is not None and current_state["mode"] != "test":
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

                    meta_extra = None
                    if current_state["mode"] == "test" and current_state["run_id"]:
                        meta_extra = {"run_id": str(current_state["run_id"])}
                    evaluator_local.process_detections(
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
                if frame is not None:
                    dets = [(o.class_name, o.confidence, o.bbox) for o in objects]
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

            def _resolve_source_local() -> tuple[str, str, Optional[str]]:
                return override_manager.get_camera_source(camera_obj.id, default_source_local)

            current_source, current_mode, current_run_id = _resolve_source_local()
            while True:
                state_local.suppress_offline_events = False
                current_state["mode"] = current_mode
                current_state["run_id"] = current_run_id
                if current_mode == "test":
                    # Suppress offline events during test runs
                    state_local.suppress_offline_events = True
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
