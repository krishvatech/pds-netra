#!/usr/bin/env python3
"""
Export a YOLO .pt model to TensorRT .engine on Jetson.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def _extract_engine_path(export_result: object) -> str | None:
    if isinstance(export_result, (str, bytes)):
        candidate = str(export_result)
        if candidate.lower().endswith(".engine"):
            return candidate
    if isinstance(export_result, (list, tuple)):
        for item in export_result:
            if isinstance(item, (str, bytes)) and str(item).lower().endswith(".engine"):
                return str(item)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Ultralytics YOLO .pt to TensorRT .engine")
    parser.add_argument("--model", required=True, help="Path to .pt model")
    parser.add_argument("--imgsz", type=int, default=640, help="Export image size")
    parser.add_argument("--half", action="store_true", help="Enable FP16 export")
    parser.add_argument("--dynamic", action="store_true", help="Enable dynamic input shapes")
    parser.add_argument("--batch", type=int, default=1, help="Export batch size")
    parser.add_argument("--force", action="store_true", help="Re-export even if engine already exists")
    args = parser.parse_args()

    try:
        from ultralytics import YOLO  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"ultralytics is required: {exc}")

    model_path = Path(args.model).expanduser().resolve()
    if model_path.suffix.lower() != ".pt":
        raise SystemExit(f"--model must be a .pt file, got: {model_path}")
    if not model_path.exists():
        raise SystemExit(f"Model file not found: {model_path}")

    expected_engine = model_path.with_suffix(".engine")
    if expected_engine.exists() and not args.force:
        print(f"Engine already exists: {expected_engine}")
        print("Use --force to export again.")
        return 0

    print("=== TensorRT Export ===")
    print(f"Model      : {model_path}")
    print(f"imgsz      : {args.imgsz}")
    print(f"half       : {bool(args.half)}")
    print(f"dynamic    : {bool(args.dynamic)}")
    print(f"batch      : {int(args.batch)}")

    model = YOLO(str(model_path))
    export_result = model.export(
        format="engine",
        imgsz=int(args.imgsz),
        half=bool(args.half),
        dynamic=bool(args.dynamic),
        batch=max(1, int(args.batch)),
        device=0,
    )

    engine_path = _extract_engine_path(export_result)
    if engine_path is not None:
        engine_file = Path(engine_path).expanduser().resolve()
        if engine_file.exists():
            print(f"Engine exported: {engine_file}")
            return 0
    if expected_engine.exists():
        print(f"Engine exported: {expected_engine}")
        return 0

    raise SystemExit(
        "TensorRT export finished but could not locate .engine output. "
        f"Expected near: {expected_engine}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
