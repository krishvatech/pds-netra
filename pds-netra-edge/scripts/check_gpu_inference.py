#!/usr/bin/env python3
"""
Quick GPU inference verification for Jetson.

Runs warmup + timed inferences with Ultralytics YOLO and prints
latency/FPS plus a simple GPU usage verdict.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import statistics
import time

try:
    import torch  # type: ignore
except Exception:  # pragma: no cover
    torch = None  # type: ignore

ALLOWED_DEVICES = {"auto", "cpu", "cuda", "cuda:0", "tensorrt"}


def torch_snapshot() -> tuple[str | None, bool, str | None]:
    if torch is None:
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


def normalize_device(raw: str) -> str:
    value = str(raw or "auto").strip().lower()
    if value == "cuda":
        return "cuda:0"
    return value


def resolve_device(requested: str, cuda_ok: bool) -> str:
    normalized = normalize_device(requested)
    if normalized not in ALLOWED_DEVICES:
        raise ValueError(f"Unsupported device: {requested}. Allowed: auto | cpu | cuda:0 | tensorrt")
    if normalized == "auto":
        return "cuda:0" if cuda_ok else "cpu"
    if normalized in {"cuda:0", "tensorrt"} and not cuda_ok:
        return "cpu"
    return normalized


def infer_backend(model_path: str, effective_device: str) -> str:
    if effective_device == "tensorrt" or model_path.lower().endswith(".engine"):
        return "tensorrt"
    return "pytorch"


def predict_device_arg(backend: str, effective_device: str):  # type: ignore[no-untyped-def]
    if backend == "tensorrt":
        return "cuda"
    if effective_device == "cuda:0":
        return 0
    return "cpu"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Jetson GPU inference path")
    parser.add_argument("--model", default=os.getenv("EDGE_YOLO_MODEL", "animal.pt"), help="Path to .pt/.engine model")
    parser.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cpu", "cuda", "cuda:0", "tensorrt"],
        help="Inference device (auto | cpu | cuda:0 | tensorrt). Alias: cuda -> cuda:0",
    )
    parser.add_argument("--imgsz", type=int, default=640, help="Inference image size")
    parser.add_argument("--warmup", type=int, default=20, help="Warmup iterations")
    parser.add_argument("--iters", type=int, default=100, help="Timed iterations")
    parser.add_argument("--conf", type=float, default=0.25, help="Detection confidence threshold")
    parser.add_argument("--iou", type=float, default=0.45, help="Detection IoU threshold")
    args = parser.parse_args()

    try:
        from ultralytics import YOLO  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"ultralytics is required: {exc}")
    try:
        import numpy as np  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"numpy is required: {exc}")

    model_path = str(Path(args.model).expanduser())
    torch_version, cuda_ok, gpu_name = torch_snapshot()
    effective_device = resolve_device(args.device, cuda_ok)
    backend = infer_backend(model_path, effective_device)
    run_device = predict_device_arg(backend, effective_device)

    print("=== GPU Inference Check ===")
    print(f"Model path                  : {model_path}")
    print(f"Requested device            : {args.device}")
    print(f"Effective device            : {effective_device}")
    print(f"Backend                     : {backend}")
    print(f"Ultralytics run device arg  : {run_device}")
    print(f"torch.__version__           : {torch_version or 'not installed'}")
    print(f"torch.cuda.is_available()   : {cuda_ok}")
    print(f"torch.cuda.get_device_name(0): {gpu_name or 'N/A'}")

    frame = np.random.randint(0, 256, (int(args.imgsz), int(args.imgsz), 3), dtype=np.uint8)
    model = YOLO(model_path)

    warmup_iters = max(0, int(args.warmup))
    timed_iters = max(1, int(args.iters))

    for _ in range(warmup_iters):
        model.predict(
            source=frame,
            device=run_device,
            imgsz=int(args.imgsz),
            conf=float(args.conf),
            iou=float(args.iou),
            verbose=False,
        )

    latencies_ms: list[float] = []
    for _ in range(timed_iters):
        t0 = time.perf_counter()
        model.predict(
            source=frame,
            device=run_device,
            imgsz=int(args.imgsz),
            conf=float(args.conf),
            iou=float(args.iou),
            verbose=False,
        )
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)

    avg_ms = statistics.fmean(latencies_ms)
    fps = 1000.0 / avg_ms if avg_ms > 0 else 0.0
    gpu_used = cuda_ok and (backend == "tensorrt" or effective_device == "cuda:0")

    print("\n=== Timed Results ===")
    print(f"Warmup iterations           : {warmup_iters}")
    print(f"Timed iterations            : {timed_iters}")
    print(f"Average latency             : {avg_ms:.2f} ms")
    print(f"FPS                         : {fps:.2f}")
    print(f"GPU USED: {'YES' if gpu_used else 'NO'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
