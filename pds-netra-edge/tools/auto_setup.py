"""
Auto-setup for edge node: downloads models if missing and runs health checks.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List
import urllib.request

from app.preflight import main as preflight_main


def _has_onnx(model_dir: Path) -> bool:
    return any(model_dir.glob("*.onnx"))


def _ensure_insightface(model: str, root: Path) -> bool:
    try:
        from insightface.utils import ensure_available  # type: ignore
    except Exception:
        print("insightface not installed; skipping InsightFace model download.")
        return False
    model_dir = ensure_available("models", model, root=str(root))
    return _has_onnx(Path(model_dir))


def _check_models() -> List[str]:
    messages: List[str] = []
    root = Path(os.getenv("INSIGHTFACE_HOME", "~/.insightface")).expanduser()
    for model in ("antelopev2", "buffalo_l"):
        model_dir = root / "models" / model
        if _has_onnx(model_dir):
            messages.append(f"InsightFace model OK: {model_dir}")
        else:
            ok = _ensure_insightface(model, root)
            if ok:
                messages.append(f"Downloaded InsightFace model: {model}")
            else:
                messages.append(f"InsightFace model missing: {model_dir}")

    yolo_model = os.getenv("EDGE_YOLO_MODEL", "animal.pt")
    model_path = Path(yolo_model).expanduser()
    if not model_path.is_absolute():
        model_path = (Path.cwd() / model_path).resolve()
    if model_path.exists():
        messages.append(f"YOLO model OK: {model_path}")
    else:
        url = os.getenv("EDGE_YOLO_MODEL_URL")
        if url:
            try:
                model_path.parent.mkdir(parents=True, exist_ok=True)
                urllib.request.urlretrieve(url, model_path)
                messages.append(f"Downloaded YOLO model from {url}")
            except Exception:
                messages.append(f"YOLO model download failed: {url}")
        else:
            try:
                from ultralytics import YOLO  # type: ignore
                YOLO(yolo_model)
                if model_path.exists():
                    messages.append(f"Downloaded YOLO model: {model_path}")
                else:
                    messages.append(f"YOLO model missing: {model_path}")
            except Exception:
                messages.append(f"YOLO model missing: {model_path}")

    try:
        import paddleocr  # type: ignore
        _ = paddleocr
        messages.append("PaddleOCR available.")
    except Exception:
        messages.append("PaddleOCR not installed (ANPR will be disabled).")
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description="Edge auto-setup")
    parser.add_argument("--config", default="config/pds_netra_config.yaml")
    args = parser.parse_args()

    print("Running model checks...")
    for msg in _check_models():
        print(f"- {msg}")

    print("Running preflight checks...")
    return preflight_main(["--config", args.config])


if __name__ == "__main__":
    raise SystemExit(main())
