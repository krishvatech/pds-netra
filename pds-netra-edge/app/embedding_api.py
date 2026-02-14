"""
Minimal API for generating face embeddings (server-safe).

Run:
  uvicorn app.embedding_api:app --host 0.0.0.0 --port 19000
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Header

from tools.generate_face_embedding import compute_embedding, load_known_faces, save_known_faces
from app.core.errors import log_exception

app = FastAPI(title="PDS Netra Embedding API", version="1.1")


def _verify_auth(authorization: str | None) -> None:
    token = os.getenv("EDGE_EMBEDDING_TOKEN")
    if not token:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization token.")
    incoming = authorization.split(" ", 1)[1].strip()
    if incoming != token:
        raise HTTPException(status_code=403, detail="Invalid authorization token.")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/v1/face-embedding")
async def face_embedding(
    person_id: str = Form(...),
    name: str = Form(...),
    role: str = Form(""),
    godown_id: str = Form(""),
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
) -> dict:
    _verify_auth(authorization)

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file upload.")

    temp_dir = Path(os.getenv("EDGE_TMP_DIR", "/tmp")) / "pds-faces"
    temp_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "").suffix or ".jpg"
    temp_path = temp_dir / f"{person_id}_{uuid.uuid4().hex}{ext}"

    try:
        temp_path.write_bytes(file_bytes)

        # This will raise ValueError for: no face / multiple faces / bad image
        embedding = compute_embedding(str(temp_path))

        # Update known_faces.json (inside container FS)
        config_path = Path(__file__).resolve().parents[1] / "config" / "known_faces.json"
        data = load_known_faces(str(config_path))

        updated = False
        for item in data:
            if item.get("person_id") == person_id:
                item["name"] = name
                item["role"] = role
                item["godown_id"] = godown_id or None
                item["embedding"] = embedding
                updated = True
                break

        if not updated:
            data.append(
                {
                    "person_id": person_id,
                    "name": name,
                    "role": role,
                    "godown_id": godown_id or None,
                    "embedding": embedding,
                }
            )

        save_known_faces(str(config_path), data)

        return {
            "status": "ok",
            "person_id": person_id,
            "name": name,
            "embedding_len": len(embedding),
        }

    except ValueError as ve:
        # Clean, user-friendly error (NO 500)
        raise HTTPException(status_code=400, detail=str(ve))

    except Exception as exc:
        # IMPORTANT: log full traceback in docker logs
        log_exception(
            app.logger,
            "Embedding failed",
            extra={"person_id": person_id, "name": name, "filename": file.filename},
            exc=exc,
        )
        msg = str(exc) or exc.__class__.__name__
        # 503 is better than 500 for "service/model not ready" situations
        raise HTTPException(status_code=503, detail=f"Embedding service error: {msg}")

    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception as exc:
            log_exception(
                app.logger,
                "Failed to cleanup temp embedding file",
                extra={"path": str(temp_path)},
                exc=exc,
            )
