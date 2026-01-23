"""
Download and verify InsightFace models for local face recognition.

Usage:
  python tools/setup_insightface_models.py --model antelopev2
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

try:
    from insightface.utils import ensure_available  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit("insightface is not installed. Install it first.") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Setup InsightFace model files.")
    parser.add_argument("--model", default="antelopev2", help="InsightFace model name (default: antelopev2).")
    parser.add_argument(
        "--root",
        default=os.getenv("INSIGHTFACE_HOME", "~/.insightface"),
        help="Model root directory (default: ~/.insightface).",
    )
    args = parser.parse_args()

    model_dir = ensure_available("models", args.model, root=args.root)
    onnx_files = list(Path(model_dir).glob("*.onnx"))
    if not onnx_files:
        raise SystemExit(f"No .onnx files found in {model_dir}. Download failed.")
    print(f"InsightFace model ready: {model_dir}")
    for path in onnx_files:
        print(f" - {path.name}")


if __name__ == "__main__":
    main()
