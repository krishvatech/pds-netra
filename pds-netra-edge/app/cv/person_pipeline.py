"""
Person detection pipeline abstraction with optional DeepStream mode.

This module keeps YOLO as the default person source and introduces a
flag-gated DeepStream adapter path. When DeepStream is unavailable, it
falls back to YOLO detections without breaking downstream event schema
contracts.
"""

from __future__ import annotations

import datetime
import logging
import os
import queue
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore

from .pipeline import DetectedObject
from .zones import bbox_center, point_in_polygon


_DEEPSTREAM_UNTRACKED_OBJECT_ID = (1 << 64) - 1


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def _parse_xy_pair(token: str) -> Optional[Tuple[float, float]]:
    parts = [p.strip() for p in token.split(",")]
    if len(parts) != 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except Exception:
        return None


def _parse_points(raw: str, min_points: int) -> Optional[List[Tuple[float, float]]]:
    points: List[Tuple[float, float]] = []
    for token in [t.strip() for t in raw.split(";") if t.strip()]:
        pair = _parse_xy_pair(token)
        if pair is None:
            return None
        points.append(pair)
    if len(points) < min_points:
        return None
    return points


def _parse_int_csv(raw: str, default: List[int]) -> List[int]:
    if not raw.strip():
        return list(default)
    out: List[int] = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.append(int(tok))
        except Exception:
            continue
    return out or list(default)


def _parse_key_value_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return values
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _resolve_points(points: List[Tuple[float, float]], width: int, height: int) -> List[Tuple[float, float]]:
    resolved: List[Tuple[float, float]] = []
    for x, y in points:
        rx = x * width if 0.0 <= x <= 1.0 else x
        ry = y * height if 0.0 <= y <= 1.0 else y
        resolved.append((float(rx), float(ry)))
    return resolved


def _bbox_in_polygon(bbox: List[int], polygon: List[Tuple[float, float]]) -> bool:
    cx, cy = bbox_center(bbox)
    if point_in_polygon(cx, cy, polygon):
        return True
    x1, y1, x2, y2 = bbox
    corners = [(x1, y1), (x1, y2), (x2, y1), (x2, y2)]
    return any(point_in_polygon(float(x), float(y), polygon) for x, y in corners)


@dataclass(frozen=True)
class PersonAnalyticsSignal:
    event_type: str
    rule_id: str
    confidence: float
    severity: str = "warning"
    bbox: Optional[List[int]] = None
    track_id: Optional[int] = None
    zone_id: Optional[str] = None
    extra: Dict[str, str] = field(default_factory=dict)


@dataclass
class _TrackState:
    last_centroid: Optional[Tuple[float, float]] = None
    last_side: Optional[float] = None
    in_roi: Optional[bool] = None
    last_seen_utc: Optional[datetime.datetime] = None
    last_line_event_utc: Optional[datetime.datetime] = None


class DeepStreamPersonAdapter:
    """
    DeepStream person adapter.

    Pipeline (per camera):
      appsrc -> videoconvert -> nvvideoconvert -> caps(NVMM/NV12)
      -> nvstreammux -> nvinfer -> (optional nvtracker) -> fakesink
    """

    def __init__(self, camera_id: str, logger: logging.Logger) -> None:
        self.camera_id = camera_id
        self.logger = logger
        self.ready = False
        self.reason = "not_initialized"

        self._Gst = None
        self._pyds = None
        self._pipeline = None
        self._appsrc = None
        self._bus = None
        self._frame_seq = 0
        self._frame_duration_ns = int(1e9 / 30)
        self._result_queue: "queue.Queue[Tuple[int, List[DetectedObject]]]" = queue.Queue(maxsize=8)
        self._source_width: Optional[int] = None
        self._source_height: Optional[int] = None
        self._timeout_sec = max(0.05, _env_float("EDGE_DEEPSTREAM_DETECT_TIMEOUT_SEC", 0.2))
        self._infer_width = max(64, _env_int("EDGE_DEEPSTREAM_INFER_WIDTH", 1280))
        self._infer_height = max(64, _env_int("EDGE_DEEPSTREAM_INFER_HEIGHT", 720))
        self._person_class_ids = set(
            _parse_int_csv(
                os.getenv("EDGE_DEEPSTREAM_PERSON_CLASS_IDS", "0"),
                default=[0],
            )
        )
        self._labels = self._load_labels_from_config()
        self._nvinfer_config = (os.getenv("EDGE_DEEPSTREAM_NVINFER_CONFIG") or "").strip()
        self._tracker_enabled = _env_bool("EDGE_DEEPSTREAM_TRACKER_ENABLED", True)
        self._tracker_config = (os.getenv("EDGE_DEEPSTREAM_TRACKER_CONFIG") or "").strip()
        self._tracker_ll_lib = (os.getenv("EDGE_DEEPSTREAM_TRACKER_LL_LIB") or "").strip()
        self._sink_sync = _env_bool("EDGE_DEEPSTREAM_SINK_SYNC", False)

        if cv2 is None:
            self.ready = False
            self.reason = "opencv_unavailable_for_deepstream_preprocess"
            return

        try:
            import gi  # type: ignore

            gi.require_version("Gst", "1.0")
            from gi.repository import Gst  # type: ignore
            import pyds  # type: ignore

            Gst.init(None)
            self._Gst = Gst
            self._pyds = pyds
        except Exception as exc:
            self.ready = False
            self.reason = f"deepstream_import_failed:{exc}"
            return

        if not self._nvinfer_config:
            self.ready = False
            self.reason = "missing_EDGE_DEEPSTREAM_NVINFER_CONFIG"
            return
        if not Path(self._nvinfer_config).expanduser().exists():
            self.ready = False
            self.reason = f"nvinfer_config_not_found:{self._nvinfer_config}"
            return

        self.ready = True
        self.reason = "deepstream_initialized"

    def _load_labels_from_config(self) -> Dict[int, str]:
        labels_raw = (os.getenv("EDGE_DEEPSTREAM_LABEL_FILE") or "").strip()
        if labels_raw:
            label_path = Path(labels_raw).expanduser()
        else:
            cfg_path_raw = (os.getenv("EDGE_DEEPSTREAM_NVINFER_CONFIG") or "").strip()
            if not cfg_path_raw:
                return {}
            cfg_path = Path(cfg_path_raw).expanduser()
            parsed = _parse_key_value_file(cfg_path)
            label_cfg = parsed.get("labelfile-path")
            if not label_cfg:
                return {}
            label_path = (cfg_path.parent / label_cfg).expanduser()
        try:
            lines = label_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            return {}
        labels: Dict[int, str] = {}
        idx = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            labels[idx] = line
            idx += 1
        return labels

    def _element_or_fail(self, factory: str, name: str):
        element = self._Gst.ElementFactory.make(factory, name)
        if element is None:
            raise RuntimeError(f"Failed to create GStreamer element '{factory}'")
        return element

    def _configure_tracker(self, tracker) -> None:
        if self._tracker_config:
            cfg_values = _parse_key_value_file(Path(self._tracker_config).expanduser())
        else:
            cfg_values = {}

        ll_lib = self._tracker_ll_lib or cfg_values.get(
            "ll-lib-file",
            "/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so",
        )
        ll_cfg = cfg_values.get("ll-config-file")
        tracker_width = int(cfg_values.get("tracker-width", "640"))
        tracker_height = int(cfg_values.get("tracker-height", "384"))
        gpu_id = int(cfg_values.get("gpu-id", "0"))

        if ll_lib:
            tracker.set_property("ll-lib-file", ll_lib)
        if ll_cfg:
            if not os.path.isabs(ll_cfg) and self._tracker_config:
                ll_cfg = str((Path(self._tracker_config).expanduser().parent / ll_cfg).resolve())
            tracker.set_property("ll-config-file", ll_cfg)
        tracker.set_property("tracker-width", tracker_width)
        tracker.set_property("tracker-height", tracker_height)
        tracker.set_property("gpu-id", gpu_id)

    def _probe_detections(self, pad, info, user_data):  # type: ignore[no-untyped-def]
        _ = pad
        _ = user_data
        try:
            gst_buffer = info.get_buffer()
            if gst_buffer is None:
                return self._Gst.PadProbeReturn.OK
            batch_meta = self._pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
            if batch_meta is None:
                return self._Gst.PadProbeReturn.OK
            frame_list = batch_meta.frame_meta_list
            while frame_list is not None:
                frame_meta = self._pyds.NvDsFrameMeta.cast(frame_list.data)
                frame_num = int(frame_meta.frame_num)
                detections: List[DetectedObject] = []
                obj_list = frame_meta.obj_meta_list
                while obj_list is not None:
                    obj_meta = self._pyds.NvDsObjectMeta.cast(obj_list.data)
                    class_id = int(obj_meta.class_id)
                    if class_id in self._person_class_ids:
                        rect = obj_meta.rect_params
                        x1 = max(0, int(rect.left))
                        y1 = max(0, int(rect.top))
                        x2 = max(x1 + 1, int(rect.left + rect.width))
                        y2 = max(y1 + 1, int(rect.top + rect.height))
                        object_id = int(getattr(obj_meta, "object_id", -1))
                        if object_id == _DEEPSTREAM_UNTRACKED_OBJECT_ID:
                            object_id = -1
                        confidence = float(getattr(obj_meta, "confidence", 0.0) or 0.0)
                        class_name = self._labels.get(class_id) or str(getattr(obj_meta, "obj_label", "")).strip() or "person"
                        detections.append(
                            DetectedObject(
                                camera_id=self.camera_id,
                                class_name=class_name,
                                confidence=confidence,
                                bbox=[x1, y1, x2, y2],
                                track_id=object_id,
                                timestamp_utc=datetime.datetime.utcnow()
                                .replace(tzinfo=datetime.timezone.utc, microsecond=0)
                                .isoformat()
                                .replace("+00:00", "Z"),
                            )
                        )
                    obj_list = obj_list.next if obj_list is not None else None

                try:
                    if self._result_queue.full():
                        _ = self._result_queue.get_nowait()
                    self._result_queue.put_nowait((frame_num, detections))
                except Exception:
                    pass

                frame_list = frame_list.next if frame_list is not None else None
        except Exception as exc:
            self.logger.debug("DeepStream probe parse failed camera=%s err=%s", self.camera_id, exc)
        return self._Gst.PadProbeReturn.OK

    def _create_pipeline(self, width: int, height: int) -> None:
        Gst = self._Gst
        if Gst is None:
            raise RuntimeError("Gst is not initialized")

        pipeline = Gst.Pipeline.new(f"ds-person-{self.camera_id}")
        if pipeline is None:
            raise RuntimeError("Failed to create DeepStream pipeline")

        appsrc = self._element_or_fail("appsrc", f"ds-appsrc-{self.camera_id}")
        videoconvert = self._element_or_fail("videoconvert", f"ds-videoconvert-{self.camera_id}")
        nvvideoconvert = self._element_or_fail("nvvideoconvert", f"ds-nvvideoconvert-{self.camera_id}")
        caps_nvmm = self._element_or_fail("capsfilter", f"ds-caps-nvmm-{self.camera_id}")
        queue_to_mux = self._element_or_fail("queue", f"ds-queue-mux-{self.camera_id}")
        streammux = self._element_or_fail("nvstreammux", f"ds-streammux-{self.camera_id}")
        nvinfer = self._element_or_fail("nvinfer", f"ds-nvinfer-{self.camera_id}")
        sink = self._element_or_fail("fakesink", f"ds-sink-{self.camera_id}")

        tracker = None
        if self._tracker_enabled:
            try:
                tracker = self._element_or_fail("nvtracker", f"ds-nvtracker-{self.camera_id}")
                self._configure_tracker(tracker)
            except Exception as exc:
                self.logger.warning("DeepStream tracker init failed camera=%s err=%s", self.camera_id, exc)
                tracker = None

        appsrc.set_property(
            "caps",
            Gst.Caps.from_string(f"video/x-raw,format=RGBA,width={width},height={height},framerate=30/1"),
        )
        appsrc.set_property("is-live", False)
        appsrc.set_property("do-timestamp", True)
        appsrc.set_property("format", Gst.Format.TIME)
        appsrc.set_property("block", True)

        caps_nvmm.set_property(
            "caps",
            Gst.Caps.from_string(
                f"video/x-raw(memory:NVMM),format=NV12,width={self._infer_width},height={self._infer_height}"
            ),
        )

        streammux.set_property("batch-size", 1)
        streammux.set_property("width", self._infer_width)
        streammux.set_property("height", self._infer_height)
        streammux.set_property("batched-push-timeout", 40000)
        streammux.set_property("live-source", False)

        nvinfer.set_property("config-file-path", str(Path(self._nvinfer_config).expanduser()))
        sink.set_property("sync", self._sink_sync)
        sink.set_property("async", False)

        for element in [appsrc, videoconvert, nvvideoconvert, caps_nvmm, queue_to_mux, streammux, nvinfer, sink]:
            pipeline.add(element)
        if tracker is not None:
            pipeline.add(tracker)

        if not appsrc.link(videoconvert):
            raise RuntimeError("Failed to link appsrc->videoconvert")
        if not videoconvert.link(nvvideoconvert):
            raise RuntimeError("Failed to link videoconvert->nvvideoconvert")
        if not nvvideoconvert.link(caps_nvmm):
            raise RuntimeError("Failed to link nvvideoconvert->capsfilter")
        if not caps_nvmm.link(queue_to_mux):
            raise RuntimeError("Failed to link capsfilter->queue")

        sink_pad = streammux.get_request_pad("sink_0")
        if sink_pad is None:
            raise RuntimeError("Failed to request nvstreammux sink_0 pad")
        src_pad = queue_to_mux.get_static_pad("src")
        if src_pad is None:
            raise RuntimeError("Failed to get queue src pad")
        if src_pad.link(sink_pad) != Gst.PadLinkReturn.OK:
            raise RuntimeError("Failed linking queue->nvstreammux sink_0")

        if tracker is not None:
            if not streammux.link(nvinfer):
                raise RuntimeError("Failed to link nvstreammux->nvinfer")
            if not nvinfer.link(tracker):
                raise RuntimeError("Failed to link nvinfer->nvtracker")
            if not tracker.link(sink):
                raise RuntimeError("Failed to link nvtracker->sink")
            probe_src = tracker
        else:
            if not streammux.link(nvinfer):
                raise RuntimeError("Failed to link nvstreammux->nvinfer")
            if not nvinfer.link(sink):
                raise RuntimeError("Failed to link nvinfer->sink")
            probe_src = nvinfer

        probe_pad = probe_src.get_static_pad("src")
        if probe_pad is None:
            raise RuntimeError("Failed to get probe pad from DeepStream pipeline")
        probe_pad.add_probe(self._Gst.PadProbeType.BUFFER, self._probe_detections, None)

        state_ret = pipeline.set_state(Gst.State.PLAYING)
        if state_ret == Gst.StateChangeReturn.FAILURE:
            pipeline.set_state(Gst.State.NULL)
            raise RuntimeError("Failed to set DeepStream pipeline to PLAYING")

        self._pipeline = pipeline
        self._appsrc = appsrc
        self._bus = pipeline.get_bus()
        self._frame_seq = 0
        self._source_width = width
        self._source_height = height
        self.logger.info(
            "DeepStream pipeline ready camera=%s infer=%sx%s tracker=%s class_ids=%s",
            self.camera_id,
            self._infer_width,
            self._infer_height,
            bool(tracker is not None),
            sorted(self._person_class_ids),
        )

    def _poll_bus_once(self) -> None:
        if self._bus is None or self._Gst is None:
            return
        msg = self._bus.timed_pop_filtered(
            0,
            self._Gst.MessageType.ERROR | self._Gst.MessageType.EOS | self._Gst.MessageType.WARNING,
        )
        if msg is None:
            return
        if msg.type == self._Gst.MessageType.ERROR:
            err, debug = msg.parse_error()
            self.logger.error("DeepStream bus error camera=%s err=%s debug=%s", self.camera_id, err, debug)
            self.reason = f"deepstream_bus_error:{err}"
            self.ready = False
            self.close()
        elif msg.type == self._Gst.MessageType.WARNING:
            warn, debug = msg.parse_warning()
            self.logger.warning("DeepStream bus warning camera=%s warn=%s debug=%s", self.camera_id, warn, debug)
        elif msg.type == self._Gst.MessageType.EOS:
            self.logger.warning("DeepStream EOS camera=%s", self.camera_id)

    def _frame_to_gst_buffer(self, frame) -> Any:  # type: ignore[no-untyped-def]
        if cv2 is None:
            raise RuntimeError("OpenCV is unavailable")
        rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
        data = rgba.tobytes()
        buffer = self._Gst.Buffer.new_allocate(None, len(data), None)
        ok, map_info = buffer.map(self._Gst.MapFlags.WRITE)
        if not ok:
            raise RuntimeError("Failed to map Gst.Buffer for DeepStream appsrc")
        try:
            map_info.data[:] = data
        finally:
            buffer.unmap(map_info)
        buffer.pts = self._frame_seq * self._frame_duration_ns
        buffer.dts = buffer.pts
        buffer.duration = self._frame_duration_ns
        buffer.offset = self._frame_seq
        self._frame_seq += 1
        return buffer

    def _read_latest_result(self) -> Optional[List[DetectedObject]]:
        deadline = time.monotonic() + self._timeout_sec
        latest: Optional[List[DetectedObject]] = None
        while time.monotonic() < deadline:
            self._poll_bus_once()
            timeout = max(0.01, deadline - time.monotonic())
            try:
                _, dets = self._result_queue.get(timeout=timeout)
                latest = dets
                while True:
                    _, dets = self._result_queue.get_nowait()
                    latest = dets
            except queue.Empty:
                continue
            except Exception:
                break
            if latest is not None:
                return latest
        return latest

    def detect(
        self,
        frame: Any,
        now_utc: datetime.datetime,
        fallback_persons: List[DetectedObject],
    ) -> Tuple[bool, List[DetectedObject], str]:
        _ = now_utc
        _ = fallback_persons
        if not self.ready:
            return False, [], self.reason
        if frame is None:
            return False, [], "deepstream_no_frame"
        try:
            frame_h, frame_w = frame.shape[:2]
            if self._pipeline is None:
                self._create_pipeline(width=int(frame_w), height=int(frame_h))
            elif self._source_width != int(frame_w) or self._source_height != int(frame_h):
                self.logger.info(
                    "DeepStream source size changed camera=%s old=%sx%s new=%sx%s; recreating pipeline",
                    self.camera_id,
                    self._source_width,
                    self._source_height,
                    int(frame_w),
                    int(frame_h),
                )
                self.close()
                self._create_pipeline(width=int(frame_w), height=int(frame_h))
            self._poll_bus_once()
            if self._appsrc is None:
                return False, [], "deepstream_appsrc_missing"
            gst_buffer = self._frame_to_gst_buffer(frame)
            flow = self._appsrc.emit("push-buffer", gst_buffer)
            if flow != self._Gst.FlowReturn.OK:
                self.close()
                return False, [], f"deepstream_push_failed:{flow}"
            dets = self._read_latest_result()
            if dets is None:
                return False, [], "deepstream_timeout"
            return True, dets, "deepstream_ok"
        except Exception as exc:
            self.close()
            self.logger.warning("DeepStream detect failed camera=%s err=%s", self.camera_id, exc)
            return False, [], f"deepstream_detect_exception:{exc}"

    def close(self) -> None:
        if self._pipeline is not None and self._Gst is not None:
            try:
                self._pipeline.set_state(self._Gst.State.NULL)
            except Exception:
                pass
        self._pipeline = None
        self._appsrc = None
        self._bus = None
        self._source_width = None
        self._source_height = None
        try:
            while True:
                self._result_queue.get_nowait()
        except Exception:
            pass

    def __del__(self) -> None:  # pragma: no cover
        self.close()


class PersonPipeline:
    def __init__(self, camera_id: str, zone_polygons: Dict[str, List[Tuple[int, int]]]) -> None:
        self.camera_id = camera_id
        self.zone_polygons = zone_polygons
        self.logger = logging.getLogger(f"PersonPipeline-{camera_id}")
        mode_raw = os.getenv("EDGE_PERSON_PIPELINE", "yolo").strip().lower()
        self.mode = mode_raw if mode_raw in {"yolo", "deepstream"} else "yolo"
        if mode_raw and mode_raw not in {"yolo", "deepstream"}:
            self.logger.warning(
                "Invalid EDGE_PERSON_PIPELINE value '%s' for camera=%s; using 'yolo'",
                mode_raw,
                camera_id,
            )
        self.roi_zone_id = (os.getenv("EDGE_PERSON_ROI_ZONE_ID") or "").strip() or None
        self.roi_events_enabled = _env_bool("EDGE_PERSON_ROI_EVENTS_ENABLED", False)
        self.line_cross_enabled = _env_bool("EDGE_PERSON_LINE_CROSS_ENABLED", False)
        self.line_id = (os.getenv("EDGE_PERSON_LINE_ID") or "line_1").strip() or "line_1"
        self.line_cooldown_sec = max(1, _env_int("EDGE_PERSON_LINE_COOLDOWN_SEC", 8))
        self.line_min_motion_px = max(0.0, _env_float("EDGE_PERSON_LINE_MIN_MOTION_PX", 6.0))
        self.track_ttl_sec = max(10, _env_int("EDGE_PERSON_TRACK_TTL_SEC", 90))
        self.event_severity = (os.getenv("EDGE_PERSON_ANALYTICS_SEVERITY") or "warning").strip() or "warning"

        self._roi_points_cfg: Optional[List[Tuple[float, float]]] = None
        self._line_cfg: Optional[Tuple[Tuple[float, float], Tuple[float, float]]] = None
        self._line_eps = 1e-6
        self._tracks: Dict[int, _TrackState] = {}
        self._fallback_logged = False
        self._deepstream: Optional[DeepStreamPersonAdapter] = None

        roi_raw = (os.getenv("EDGE_PERSON_ROI_POLYGON") or "").strip()
        if roi_raw:
            parsed_roi = _parse_points(roi_raw, min_points=3)
            if parsed_roi is not None:
                self._roi_points_cfg = parsed_roi
            else:
                self.logger.warning("Invalid EDGE_PERSON_ROI_POLYGON format for camera=%s", camera_id)

        line_raw = (os.getenv("EDGE_PERSON_LINE") or "").strip()
        if line_raw:
            parsed_line = _parse_points(line_raw, min_points=2)
            if parsed_line is not None and len(parsed_line) >= 2:
                self._line_cfg = (parsed_line[0], parsed_line[1])
            else:
                self.logger.warning("Invalid EDGE_PERSON_LINE format for camera=%s", camera_id)

        if self.mode == "deepstream":
            self._deepstream = DeepStreamPersonAdapter(camera_id, self.logger)

        self._enabled = bool(
            self.mode == "deepstream"
            or self.roi_events_enabled
            or (self.line_cross_enabled and self._line_cfg is not None)
        )
        if self.line_cross_enabled and self._line_cfg is None:
            self.logger.warning(
                "Person line-cross analytics requested but EDGE_PERSON_LINE is missing for camera=%s",
                camera_id,
            )

        self.logger.info(
            "Person pipeline camera=%s mode=%s enabled=%s roi_events=%s line_cross=%s roi_zone_id=%s",
            self.camera_id,
            self.mode,
            self._enabled,
            self.roi_events_enabled,
            self.line_cross_enabled,
            self.roi_zone_id,
        )

    def is_enabled(self) -> bool:
        return self._enabled

    def close(self) -> None:
        if self._deepstream is not None:
            self._deepstream.close()

    @staticmethod
    def _line_side(
        point: Tuple[float, float],
        line: Tuple[Tuple[float, float], Tuple[float, float]],
    ) -> float:
        (x1, y1), (x2, y2) = line
        px, py = point
        return ((x2 - x1) * (py - y1)) - ((y2 - y1) * (px - x1))

    def _resolve_roi_polygon(self, width: int, height: int) -> Optional[List[Tuple[float, float]]]:
        if self._roi_points_cfg:
            resolved = _resolve_points(self._roi_points_cfg, width, height)
            return resolved if len(resolved) >= 3 else None
        if self.roi_zone_id and self.roi_zone_id in self.zone_polygons:
            zone_pts = [(float(x), float(y)) for x, y in self.zone_polygons[self.roi_zone_id]]
            return _resolve_points(zone_pts, width, height) if zone_pts else None
        return None

    def _resolve_line(
        self,
        width: int,
        height: int,
    ) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
        if self._line_cfg is None:
            return None
        p1, p2 = self._line_cfg
        rp1 = _resolve_points([p1], width, height)[0]
        rp2 = _resolve_points([p2], width, height)[0]
        return rp1, rp2

    def _cleanup_stale_tracks(self, now_utc: datetime.datetime) -> None:
        stale_ids: List[int] = []
        for track_id, state in self._tracks.items():
            if state.last_seen_utc is None:
                stale_ids.append(track_id)
                continue
            if (now_utc - state.last_seen_utc).total_seconds() > self.track_ttl_sec:
                stale_ids.append(track_id)
        for track_id in stale_ids:
            self._tracks.pop(track_id, None)

    def _build_extra(self, extra: Dict[str, Any]) -> Dict[str, str]:
        payload: Dict[str, str] = {}
        for key, value in extra.items():
            if value is None:
                continue
            payload[str(key)] = str(value)
        return payload

    def process(
        self,
        objects: List[DetectedObject],
        frame: Any,
        now_utc: datetime.datetime,
    ) -> Tuple[List[DetectedObject], List[PersonAnalyticsSignal]]:
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=datetime.timezone.utc)

        person_objects = [obj for obj in objects if str(obj.class_name).lower() == "person"]
        non_person_objects = [obj for obj in objects if str(obj.class_name).lower() != "person"]
        selected_persons = person_objects
        person_source = "yolo"

        if self.mode == "deepstream" and self._deepstream is not None and frame is not None:
            ok, ds_people, reason = self._deepstream.detect(frame, now_utc, person_objects)
            if ok:
                selected_persons = ds_people
                person_source = "deepstream"
            elif not self._fallback_logged:
                self.logger.warning(
                    "DeepStream mode requested for camera=%s but unavailable (%s). Falling back to YOLO persons.",
                    self.camera_id,
                    reason,
                )
                self._fallback_logged = True

        merged_objects = objects
        if person_source == "deepstream":
            merged_objects = [*non_person_objects, *selected_persons]

        if not self._enabled or frame is None:
            return merged_objects, []

        height = int(getattr(frame, "shape", [0, 0])[0]) if hasattr(frame, "shape") else 0
        width = int(getattr(frame, "shape", [0, 0])[1]) if hasattr(frame, "shape") else 0
        if width <= 0 or height <= 0:
            return merged_objects, []

        roi_polygon = self._resolve_roi_polygon(width, height)
        line = self._resolve_line(width, height) if self.line_cross_enabled else None
        signals: List[PersonAnalyticsSignal] = []

        for obj in selected_persons:
            track_id = int(getattr(obj, "track_id", -1))
            bbox = getattr(obj, "bbox", None)
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue
            if track_id < 0:
                continue
            confidence = float(getattr(obj, "confidence", 0.0))
            state = self._tracks.setdefault(track_id, _TrackState())
            centroid = bbox_center(bbox)

            if self.roi_events_enabled and roi_polygon is not None:
                in_roi = _bbox_in_polygon(bbox, roi_polygon)
                if state.in_roi is None:
                    state.in_roi = in_roi
                elif in_roi != state.in_roi:
                    event_type = "PERSON_ROI_ENTER" if in_roi else "PERSON_ROI_EXIT"
                    signals.append(
                        PersonAnalyticsSignal(
                            event_type=event_type,
                            rule_id="PERSON_ROI_ANALYTICS",
                            confidence=confidence,
                            severity=self.event_severity,
                            bbox=bbox,
                            track_id=track_id,
                            zone_id=self.roi_zone_id,
                            extra=self._build_extra(
                                {
                                    "pipeline": person_source,
                                    "roi_zone_id": self.roi_zone_id,
                                    "roi_state": "inside" if in_roi else "outside",
                                }
                            ),
                        )
                    )
                    state.in_roi = in_roi

            if line is not None:
                side = self._line_side(centroid, line)
                if (
                    state.last_side is not None
                    and abs(side) > self._line_eps
                    and abs(state.last_side) > self._line_eps
                    and (side * state.last_side) < 0
                    and state.last_centroid is not None
                ):
                    movement_px = ((centroid[0] - state.last_centroid[0]) ** 2 + (centroid[1] - state.last_centroid[1]) ** 2) ** 0.5
                    cooldown_ok = (
                        state.last_line_event_utc is None
                        or (now_utc - state.last_line_event_utc).total_seconds() >= self.line_cooldown_sec
                    )
                    if movement_px >= self.line_min_motion_px and cooldown_ok:
                        direction = "A_TO_B" if state.last_side < 0 < side else "B_TO_A"
                        signals.append(
                            PersonAnalyticsSignal(
                                event_type="PERSON_LINE_CROSS",
                                rule_id="PERSON_LINE_CROSS_ANALYTICS",
                                confidence=confidence,
                                severity=self.event_severity,
                                bbox=bbox,
                                track_id=track_id,
                                zone_id=self.roi_zone_id,
                                extra=self._build_extra(
                                    {
                                        "pipeline": person_source,
                                        "line_id": self.line_id,
                                        "direction": direction,
                                        "movement_px": f"{movement_px:.2f}",
                                    }
                                ),
                            )
                        )
                        state.last_line_event_utc = now_utc
                state.last_side = side

            state.last_centroid = centroid
            state.last_seen_utc = now_utc

        self._cleanup_stale_tracks(now_utc)
        return merged_objects, signals
