"""
Generate or update known face embeddings from a reference image.

Usage:
  python tools/generate_face_embedding.py --image path/to/img.jpg --person-id P1 --name Alice --role staff
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.errors import safe_json_dump_atomic, safe_json_load

try:
    import numpy as np  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit("numpy is not installed. Install it to use this tool.") from exc

try:
    import cv2  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit("opencv-python is not installed. Install it to use this tool.") from exc

try:
    from insightface.app import FaceAnalysis  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit("insightface is not installed. Install it to use this tool.") from exc


logger = logging.getLogger("generate_face_embedding")

_FACE_APP: Optional[FaceAnalysis] = None
_FACE_LOCK = threading.Lock()
_INSIGHTFACE_MODEL_NAME = os.getenv("INSIGHTFACE_MODEL_NAME", "antelopev2")
_INSIGHTFACE_MODELS_DIR = Path("/root/.insightface/models")


def _is_model_dir_incomplete(model_dir: Path) -> bool:
    if not model_dir.exists():
        return False
    if not model_dir.is_dir():
        return True

    onnx_files = list(model_dir.glob("*.onnx"))
    if not onnx_files:
        return True

    for onnx_file in onnx_files:
        try:
            if onnx_file.stat().st_size <= 0:
                return True
        except OSError:
            return True

    has_detection = any("det" in p.name.lower() or "scrfd" in p.name.lower() for p in onnx_files)
    has_recognition = any("glint" in p.name.lower() or "r100" in p.name.lower() for p in onnx_files)
    return not (has_detection and has_recognition)


def _fix_nested_model_dir(model_name: str) -> bool:
    model_dir = _INSIGHTFACE_MODELS_DIR / model_name
    nested_dir = model_dir / model_name
    if not nested_dir.exists() or not nested_dir.is_dir():
        return False

    moved_any = False
    for child in nested_dir.iterdir():
        target = model_dir / child.name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        shutil.move(str(child), str(target))
        moved_any = True

    nested_dir.rmdir()
    if moved_any:
        logger.warning("Fixed nested InsightFace model directory: %s", nested_dir)
    return moved_any


def _delete_model_dir(model_name: str) -> bool:
    model_dir = _INSIGHTFACE_MODELS_DIR / model_name
    if not model_dir.exists():
        return False
    if model_dir.is_dir():
        shutil.rmtree(model_dir)
    else:
        model_dir.unlink()
    logger.warning("Deleted incomplete/corrupt InsightFace model directory: %s", model_dir)
    return True


def _init_face_app(model_name: str) -> FaceAnalysis:
    logger.info("Initializing InsightFace FaceAnalysis(name=%s, provider=CPU)...", model_name)
    app = FaceAnalysis(name=model_name, providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(640, 640))
    logger.info("InsightFace initialized OK.")
    return app


def _get_face_app() -> FaceAnalysis:
    """
    Initialize InsightFace once per process and cache globally.
    Prevents repeated model download/unzip/load on every request.
    """
    global _FACE_APP
    if _FACE_APP is not None:
        return _FACE_APP

    with _FACE_LOCK:
        if _FACE_APP is not None:
            return _FACE_APP

        _INSIGHTFACE_MODELS_DIR.mkdir(parents=True, exist_ok=True)

        try:
            _FACE_APP = _init_face_app(_INSIGHTFACE_MODEL_NAME)
            return _FACE_APP
        except AssertionError:
            logger.exception("InsightFace init assertion failed. Attempting model cache self-heal.")

            nested_fixed = _fix_nested_model_dir(_INSIGHTFACE_MODEL_NAME)
            model_dir = _INSIGHTFACE_MODELS_DIR / _INSIGHTFACE_MODEL_NAME
            deleted_corrupt = False
            if _is_model_dir_incomplete(model_dir):
                deleted_corrupt = _delete_model_dir(_INSIGHTFACE_MODEL_NAME)

            logger.warning(
                "Retrying InsightFace init after self-heal (nested_fixed=%s, deleted_corrupt=%s).",
                nested_fixed,
                deleted_corrupt,
            )
            try:
                _FACE_APP = _init_face_app(_INSIGHTFACE_MODEL_NAME)
                return _FACE_APP
            except Exception as second_exc:
                raise RuntimeError(
                    f"InsightFace detection model is missing for '{_INSIGHTFACE_MODEL_NAME}'. "
                    f"Model cache path: {_INSIGHTFACE_MODELS_DIR / _INSIGHTFACE_MODEL_NAME}. "
                    "Clean model cache and allow model download to complete."
                ) from second_exc
        except Exception as exc:
            raise RuntimeError(f"InsightFace initialization failed: {exc}") from exc


def load_known_faces(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    data = safe_json_load(path, [], logger=logging.getLogger("known_faces"))
    return data if isinstance(data, list) else []


def save_known_faces(path: str, data: List[Dict[str, Any]]) -> None:
    ok = safe_json_dump_atomic(path, data, logger=logging.getLogger("known_faces"))
    if not ok:
        logging.getLogger("known_faces").warning("Failed to save known faces path=%s", path)


def compute_embedding(image_path: str) -> List[float]:
    fa = _get_face_app()

    raw = np.fromfile(image_path, dtype=np.uint8)
    if raw.size == 0:
        raise ValueError("Unable to read image bytes.")

    frame = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Unable to decode image.")

    faces = fa.get(frame)
    if not faces:
        raise ValueError("No face detected. Upload a clear single-face photo.")
    if len(faces) > 1:
        raise ValueError("Multiple faces detected. Upload a single-face photo.")

    emb = faces[0].embedding.astype("float32")
    norm = float(np.linalg.norm(emb))
    if norm > 0:
        emb = emb / norm
    return [float(x) for x in emb]


def upsert_person(
    data: List[Dict[str, Any]],
    person_id: str,
    name: str,
    role: str,
    embedding: List[float],
) -> List[Dict[str, Any]]:
    updated = False
    for item in data:
        if item.get("person_id") == person_id:
            item["name"] = name
            item["role"] = role
            item["embedding"] = embedding
            updated = True
            break
    if not updated:
        data.append(
            {
                "person_id": person_id,
                "name": name,
                "role": role,
                "embedding": embedding,
            }
        )
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate or update known face embeddings.")
    parser.add_argument("--image", required=True, help="Path to a face image file.")
    parser.add_argument("--person-id", required=True, help="Unique person ID.")
    parser.add_argument("--name", required=True, help="Person name.")
    parser.add_argument("--role", required=True, help="Person role.")
    parser.add_argument(
        "--output",
        default="config/known_faces.json",
        help="Output JSON file (default: config/known_faces.json).",
    )
    args = parser.parse_args()

    embedding = compute_embedding(args.image)
    data = load_known_faces(args.output)
    data = upsert_person(data, args.person_id, args.name, args.role, embedding)
    save_known_faces(args.output, data)
    print(f"Saved embedding for {args.person_id} to {args.output}")


if __name__ == "__main__":
    main()
