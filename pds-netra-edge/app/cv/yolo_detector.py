"""
Wrapper around the Ultralytics YOLO model for object detection.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple
import logging
import os
import shlex

try:
    from ultralytics import YOLO  # type: ignore
except ImportError:
    YOLO = None  # type: ignore

try:
    import torch  # type: ignore
except Exception:  # pragma: no cover
    torch = None  # type: ignore


class YoloDetector:
    """
    YOLO detector wrapper for performing object detection on frames.
    """

    def __init__(
        self,
        model_name: str = "animal.pt",
        device: str = "cpu",
        tracker_name: str = "bytetrack.yaml",
        track_persist: bool = True,
        track_conf: float | None = None,
        track_iou: float | None = None,
        conf: float | None = None,
        iou: float | None = None,
        imgsz: int | None = None,
        classes: list[int] | None = None,
        max_det: int | None = None,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        if YOLO is None:
            raise RuntimeError("ultralytics is not installed; please install ultralytics")

        self.model_name = model_name
        self.device = device
        self.tracker_name = tracker_name
        self.track_persist = track_persist
        self.track_conf = track_conf
        self.track_iou = track_iou
        self.conf = conf
        self.iou = iou
        self.imgsz = imgsz
        self.classes = classes
        self.max_det = max_det

        self.runtime_device = self._normalize_device(device)
        self.backend = "tensorrt" if self._should_use_tensorrt(model_name, self.runtime_device) else "pytorch"
        if self.backend == "pytorch" and self.runtime_device == "cuda:0" and not self._cuda_available():
            self.logger.warning(
                "CUDA requested but unavailable. Falling back to CPU inference for model=%s",
                model_name,
            )
            self.runtime_device = "cpu"
        self.model_path = self._resolve_model_path(model_name)
        if self.backend == "tensorrt" and not self._cuda_available():
            if self.model_path.lower().endswith(".pt"):
                self.logger.warning(
                    "TensorRT requested but CUDA unavailable. Falling back to PyTorch CPU for model=%s",
                    self.model_path,
                )
                self.backend = "pytorch"
                self.runtime_device = "cpu"
            else:
                raise RuntimeError(
                    f"TensorRT engine requires CUDA, but torch.cuda.is_available() is False: {self.model_path}"
                )
        if self.backend == "tensorrt":
            self.model_path = self._resolve_or_export_tensorrt_engine(self.model_path)

        self.model = YOLO(self.model_path)
        if self.backend == "pytorch":
            self._move_model_to_runtime_device()
        self.names = self.model.names
        self.label_overrides = self._load_label_overrides()

        self.logger.info(
            "Loaded YOLO model=%s backend=%s requested_device=%s runtime_device=%s "
            "conf=%s iou=%s imgsz=%s classes=%s max_det=%s",
            self.model_path,
            self.backend,
            device,
            self.runtime_device,
            self.conf,
            self.iou,
            self.imgsz,
            self.classes,
            self.max_det,
        )

    def _normalize_device(self, device: str) -> str:
        v = (device or "cpu").strip().lower()
        if v == "cuda":
            return "cuda:0"
        if v == "auto":
            if torch is not None:
                try:
                    return "cuda:0" if torch.cuda.is_available() else "cpu"
                except Exception:
                    return "cpu"
            return "cpu"
        return v

    @staticmethod
    def _cuda_available() -> bool:
        if torch is None:
            return False
        try:
            return bool(torch.cuda.is_available())
        except Exception:
            return False

    def _should_use_tensorrt(self, model_name: str, device: str) -> bool:
        if device == "tensorrt":
            return True
        return model_name.lower().endswith(".engine")

    def _resolve_model_path(self, model_name: str) -> str:
        p = Path(model_name).expanduser()
        return str(p)

    def _move_model_to_runtime_device(self) -> None:
        if self.runtime_device != "cuda:0":
            return
        if torch is None:
            self.logger.warning("Torch is unavailable; cannot move model to CUDA.")
            return
        try:
            if not torch.cuda.is_available():
                self.logger.warning("CUDA requested but torch.cuda.is_available() is False.")
                return
            self.model.to("cuda:0")
        except Exception as exc:
            self.logger.warning("Failed to move YOLO model to CUDA: %s", exc)

    @staticmethod
    def _extract_exported_engine_path(export_result: object) -> str | None:
        if isinstance(export_result, (str, bytes)):
            candidate = str(export_result)
            if candidate.lower().endswith(".engine"):
                return candidate
        if isinstance(export_result, (list, tuple)):
            for item in export_result:
                if isinstance(item, (str, bytes)) and str(item).lower().endswith(".engine"):
                    return str(item)
        return None

    def _resolve_or_export_tensorrt_engine(self, model_path: str) -> str:
        model_file = Path(model_path).expanduser()
        if model_file.suffix.lower() == ".engine":
            if model_file.exists():
                return str(model_file)
            # If .engine explicitly provided but missing, try matching .pt.
            pt_candidate = model_file.with_suffix(".pt")
            if not pt_candidate.exists():
                raise RuntimeError(f"TensorRT engine not found: {model_file}")
            model_file = pt_candidate

        if model_file.suffix.lower() != ".pt":
            raise RuntimeError(
                f"TensorRT mode requires a .pt model or .engine file, got: {model_file}"
            )

        engine_file = model_file.with_suffix(".engine")
        if engine_file.exists():
            return str(engine_file)

        export_cmd_hint = (
            "python3 scripts/export_engine.py "
            f"--model {shlex.quote(str(model_file))} --imgsz {self.imgsz or self._default_imgsz()} --half --dynamic"
        )
        self.logger.warning(
            "TensorRT engine not found at %s. Exporting from %s on first run. "
            "Equivalent helper command: %s",
            engine_file,
            model_file,
            export_cmd_hint,
        )

        export_model = YOLO(str(model_file))
        export_kwargs = {
            "format": "engine",
            "device": 0,
            "imgsz": int(self.imgsz if self.imgsz is not None else self._default_imgsz()),
        }
        if os.getenv("EDGE_TRT_HALF", "1").strip().lower() in {"1", "true", "yes", "y"}:
            export_kwargs["half"] = True
        if os.getenv("EDGE_TRT_DYNAMIC", "0").strip().lower() in {"1", "true", "yes", "y"}:
            export_kwargs["dynamic"] = True
        batch_raw = os.getenv("EDGE_TRT_BATCH", "").strip()
        if batch_raw:
            try:
                export_kwargs["batch"] = max(1, int(batch_raw))
            except Exception:
                pass
        workspace = os.getenv("EDGE_TRT_WORKSPACE_GB", "").strip()
        if workspace:
            try:
                export_kwargs["workspace"] = float(workspace)
            except Exception:
                pass

        export_result = export_model.export(**export_kwargs)
        exported_engine = self._extract_exported_engine_path(export_result)
        if exported_engine:
            exported_path = Path(exported_engine).expanduser()
            if exported_path.exists():
                return str(exported_path)
        if engine_file.exists():
            return str(engine_file)
        raise RuntimeError(f"TensorRT export completed but engine file was not found: {engine_file}")

    def _predict_device_arg(self):  # type: ignore[no-untyped-def]
        if self.backend == "tensorrt":
            return "cuda"
        if self.runtime_device == "cuda:0":
            return 0
        return "cpu"

    def _class_name(self, class_id: int) -> str:
        names = self.names
        if isinstance(names, dict):
            return str(names.get(class_id, class_id))
        if isinstance(names, list) and 0 <= class_id < len(names):
            return str(names[class_id])
        return str(class_id)

    @staticmethod
    def _load_label_overrides() -> dict[str, str]:
        """
        Load optional label overrides from EDGE_CLASS_LABEL_OVERRIDES.
        Format: "bull:Buffalo,cattle:Buffalo"
        """
        raw = os.getenv("EDGE_CLASS_LABEL_OVERRIDES", "").strip()
        overrides: dict[str, str] = {}
        if not raw:
            return overrides
        for item in raw.split(","):
            item = item.strip()
            if not item or ":" not in item:
                continue
            src, dst = item.split(":", 1)
            src = src.strip().lower()
            dst = dst.strip()
            if not src or not dst:
                continue
            overrides[src] = dst
        return overrides

    def _apply_label_override(self, class_name: str) -> str:
        if not self.label_overrides:
            return class_name
        return self.label_overrides.get(class_name.lower(), class_name)

    def _default_imgsz(self) -> int:
        """
        Never return None.
        Use higher default for anpr/plate models.
        """
        name = (self.model_name or "").lower()
        if ("anpr" in name) or ("plate" in name) or ("platemodel" in name):
            # Plates are small -> higher imgsz helps a lot
            try:
                return int(os.getenv("EDGE_ANPR_IMGSZ", "960"))
            except Exception:
                return 960
        try:
            return int(os.getenv("EDGE_YOLO_IMGSZ", "640"))
        except Exception:
            return 640

    def detect(self, frame) -> List[Tuple[str, float, List[int]]]:
        """
        Returns list of (class_name, confidence, [x1,y1,x2,y2])
        """
        # Build kwargs safely: do NOT pass imgsz=None, conf=None, iou=None etc
        predict_kwargs = {
            "source": frame,
            "device": self._predict_device_arg(),
            "verbose": False,
        }

        if self.conf is not None:
            predict_kwargs["conf"] = float(self.conf)
        if self.iou is not None:
            predict_kwargs["iou"] = float(self.iou)
        if self.classes is not None:
            predict_kwargs["classes"] = self.classes
        if self.max_det is not None:
            predict_kwargs["max_det"] = int(self.max_det)

        # imgsz must be int or [h,w], never None
        predict_kwargs["imgsz"] = self.imgsz if self.imgsz is not None else self._default_imgsz()

        results0 = self.model.predict(**predict_kwargs)[0]

        detections: List[Tuple[str, float, List[int]]] = []
        for box in results0.boxes:
            class_id = int(box.cls.item())
            class_name = self._apply_label_override(self._class_name(class_id))
            confidence = float(box.conf.item())
            xyxy = box.xyxy.tolist()[0]
            bbox = [int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])]
            detections.append((class_name, confidence, bbox))

        return detections

    def track(self, frame) -> List[Tuple[int, Tuple[str, float, List[int]]]]:
        """
        Run ByteTrack-based tracking on a single frame.

        Returns:
            [(track_id, (class_name, confidence, [x1,y1,x2,y2]))]
        """
        track_kwargs = {
            "device": self._predict_device_arg(),
            "persist": self.track_persist,
            "tracker": self.tracker_name,
            "verbose": False,
        }
        if self.track_conf is not None:
            track_kwargs["conf"] = float(self.track_conf)
        if self.track_iou is not None:
            track_kwargs["iou"] = float(self.track_iou)

        results0 = self.model.track(frame, **track_kwargs)[0]

        tracked: List[Tuple[int, Tuple[str, float, List[int]]]] = []
        for box in results0.boxes:
            class_id = int(box.cls.item())
            class_name = self._apply_label_override(self._class_name(class_id))
            confidence = float(box.conf.item()) if box.conf is not None else 0.0
            xyxy = box.xyxy.tolist()[0]
            bbox = [int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])]
            track_id = int(box.id.item()) if box.id is not None else -1
            tracked.append((track_id, (class_name, confidence, bbox)))

        return tracked
