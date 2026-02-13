#!/usr/bin/env python3
"""
Quick GPU inference verifier for Jetson.

Runs warmup + timed YOLO inferences and prints latency/FPS plus device status.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.cv.yolo_detector import YoloDetector


ALLOWED_DEVICES = {"cpu", "cuda:0", "tensorrt"}


def normalize_device(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip().lower()
    if not value:
        return None
    if value == "cuda":
        return "cuda:0"
    return value


def torch_snapshot() -> tuple[str | None, bool, str | None]:
    try:
        import torch  # type: ignore
    except Exception:
        return None, False, None
    version = getattr(torch, "__version__", None)
    try:
        cuda_ok = bool(torch.cuda.is_available())
    except Exception:
        cuda_ok = False
    gpu_name = None
    if cuda_ok:
        try:
            gpu_name = str(torch.cuda.get_device_name(0))
        except Exception:
            gpu_name = None
    return version, cuda_ok, gpu_name


def resolve_device(requested: str | None, cuda_ok: bool) -> str:
    normalized = normalize_device(requested)
    if normalized and normalized not in ALLOWED_DEVICES:
        raise ValueError(f"Unsupported device: {requested}. Allowed: cpu | cuda:0 | tensorrt")
    if normalized is None:
        return "cuda:0" if cuda_ok else "cpu"
    if normalized in {"cuda:0", "tensorrt"} and not cuda_ok:
        return "cpu"
    return normalized


def load_frame(frame_path: str | None, imgsz: int):
    if not frame_path:
        import numpy as np

        return np.zeros((imgsz, imgsz, 3), dtype=np.uint8)
    try:
        import cv2  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"cv2 is required when --frame is used: {exc}") from exc
    image = cv2.imread(frame_path)
    if image is None:
        raise RuntimeError(f"Failed to read frame image: {frame_path}")
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description="Check if YOLO inference is using Jetson GPU")
    parser.add_argument("--model", default=os.getenv("EDGE_YOLO_MODEL", "animal.pt"), help="Path to .pt/.engine model")
    parser.add_argument(
        "--device",
        default=None,
        choices=["cpu", "cuda:0", "tensorrt"],
        help="Inference device (default: auto cuda:0 if available else cpu)",
    )
    parser.add_argument("--imgsz", type=int, default=640, help="Inference image size")
    parser.add_argument("--warmup", type=int, default=15, help="Warmup inference iterations")
    parser.add_argument("--runs", type=int, default=50, help="Timed inference iterations")
    parser.add_argument("--frame", type=str, default=None, help="Optional path to a JPG/PNG frame for inference")
    parser.add_argument("--conf", type=float, default=0.25, help="Detection confidence threshold")
    parser.add_argument("--iou", type=float, default=0.45, help="Detection IoU threshold")
    args = parser.parse_args()

    torch_version, cuda_ok, gpu_name = torch_snapshot()
    effective_device = resolve_device(args.device, cuda_ok)

    print("=== GPU Inference Check ===")
    print(f"Model path                : {args.model}")
    print(f"Requested device          : {args.device or 'auto'}")
    print(f"Effective device          : {effective_device}")
    print(f"torch.__version__         : {torch_version or 'not installed'}")
    print(f"torch.cuda.is_available() : {cuda_ok}")
    print(f"torch.cuda.get_device_name(0): {gpu_name or 'N/A'}")

    frame = load_frame(args.frame, args.imgsz)
    detector = YoloDetector(
        model_name=args.model,
        device=effective_device,
        conf=args.conf,
        iou=args.iou,
        imgsz=args.imgsz,
    )
    print(f"Detector backend          : {detector.backend}")
    print("Starting warmup...")
    for _ in range(max(0, args.warmup)):
        detector.detect(frame)

    print("Starting timed run...")
    latencies_ms: list[float] = []
    for _ in range(max(1, args.runs)):
        t0 = time.perf_counter()
        detector.detect(frame)
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)

    avg_ms = statistics.fmean(latencies_ms)
    min_ms = min(latencies_ms)
    max_ms = max(latencies_ms)
    fps = 1000.0 / avg_ms if avg_ms > 0 else 0.0
    gpu_used = cuda_ok and (effective_device in {"cuda:0", "tensorrt"})

    print("\n=== Timed Results ===")
    print(f"Warmup runs               : {max(0, args.warmup)}")
    print(f"Timed runs                : {max(1, args.runs)}")
    print(f"Average latency           : {avg_ms:.2f} ms")
    print(f"Min latency               : {min_ms:.2f} ms")
    print(f"Max latency               : {max_ms:.2f} ms")
    print(f"Approx FPS                : {fps:.2f}")
    print(f"GPU used                  : {gpu_used}")
    if gpu_used:
        print("Verdict                   : GPU inference path active")
    else:
        print("Verdict                   : CPU path active or CUDA unavailable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
