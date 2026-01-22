"""
Generate or update known face embeddings from a reference image.

Usage:
  python tools/generate_face_embedding.py --image path/to/img.jpg --person-id P1 --name Alice --role staff
"""

from __future__ import annotations

import argparse
import json
import os
from typing import List, Dict, Any

try:
    import numpy as np  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit("numpy is not installed. Install it to use this tool.") from exc

try:
    from insightface.app import FaceAnalysis  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit("insightface is not installed. Install it to use this tool.") from exc


def load_known_faces(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_known_faces(path: str, data: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def compute_embedding(image_path: str) -> List[float]:
    app = FaceAnalysis(name="antelopev2")
    app.prepare(ctx_id=-1, det_size=(640, 640))
    img = np.fromfile(image_path, dtype=np.uint8)
    if img.size == 0:
        raise ValueError("Unable to read image bytes.")
    import cv2  # type: ignore
    frame = cv2.imdecode(img, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Unable to decode image.")
    faces = app.get(frame)
    if not faces:
        raise ValueError("No face found in the image.")
    if len(faces) > 1:
        raise ValueError("Multiple faces found in the image. Provide a single face.")
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
