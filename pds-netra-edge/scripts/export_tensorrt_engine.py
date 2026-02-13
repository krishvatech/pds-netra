#!/usr/bin/env python3
"""
Export a YOLO .pt model to TensorRT .engine on Jetson.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Ultralytics YOLO model to TensorRT engine")
    parser.add_argument("--model", required=True, help="Path to YOLO .pt model")
    parser.add_argument("--imgsz", type=int, default=640, help="Export image size")
    parser.add_argument("--workspace-gb", type=float, default=4.0, help="TensorRT workspace size in GB")
    parser.add_argument("--half", action="store_true", help="Enable FP16 engine export")
    parser.add_argument("--force", action="store_true", help="Overwrite export if engine exists")
    args = parser.parse_args()

    model_path = Path(args.model).expanduser().resolve()
    if model_path.suffix.lower() != ".pt":
        raise SystemExit(f"--model must point to a .pt file, got: {model_path}")
    if not model_path.exists():
        raise SystemExit(f"Model file not found: {model_path}")

    engine_path = model_path.with_suffix(".engine")
    if engine_path.exists() and not args.force:
        print(f"Engine already exists: {engine_path}")
        print("Use --force to export again.")
        return 0

    print("Exporting TensorRT engine...")
    print(f"Source PT      : {model_path}")
    print(f"Target engine  : {engine_path}")
    print(f"imgsz          : {args.imgsz}")
    print(f"workspace_gb   : {args.workspace_gb}")
    print(f"half           : {args.half}")

    from ultralytics import YOLO  # type: ignore

    model = YOLO(str(model_path))
    export_result = model.export(
        format="engine",
        device=0,
        imgsz=args.imgsz,
        workspace=args.workspace_gb,
        half=bool(args.half),
    )

    print(f"Export result  : {export_result}")
    if not engine_path.exists():
        raise SystemExit(f"Export finished but engine file not found at {engine_path}")
    print(f"Engine ready   : {engine_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
