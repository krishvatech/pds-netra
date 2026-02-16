"""
Minimal API for generating face embeddings (server-safe).

Run:
  uvicorn app.embedding_api:app --host 0.0.0.0 --port 19000
"""

from __future__ import annotations

import os
import uuid
import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Header

from tools.generate_face_embedding import (
    compute_embedding,
    load_known_faces,
    save_known_faces,
)
from app.core.errors import log_exception

app = FastAPI(title="PDS Netra Embedding API", version="1.2")

# ✅ Proper logger (NOT app.logger)
logger = logging.getLogger("embedding_api")


def _known_faces_config_path() -> Path:
    env_path = (os.getenv("KNOWN_FACES_FILE") or "").strip()
    if env_path:
        return Path(env_path).expanduser()
    return Path(__file__).resolve().parents[1] / "config" / "known_faces.json"


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


@app.get("/api/v1/known-faces")
def known_faces(
    godown_id: str | None = None,
    authorization: str | None = Header(default=None),
) -> dict:
    _verify_auth(authorization)

    config_path = _known_faces_config_path()
    if not config_path.exists():
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            save_known_faces(str(config_path), [])
            logger.info("Created missing known faces config at %s", config_path)
        except Exception as exc:
            log_exception(
                logger,
                "Failed to initialize known faces config",
                extra={"path": str(config_path)},
                exc=exc,
            )
            raise HTTPException(status_code=503, detail=f"Unable to initialize known faces config at {config_path}")

    data = load_known_faces(str(config_path))
    items = data if isinstance(data, list) else []
    if godown_id:
        filtered: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            item_godown_id = item.get("godown_id")
            if not item_godown_id or str(item_godown_id) == godown_id:
                filtered.append(item)
        items = filtered

    return {"status": "ok", "count": len(items), "data": items}


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

        # Will raise ValueError for:
        # - no face
        # - multiple faces
        # - bad image
        embedding = compute_embedding(str(temp_path))

        config_path = _known_faces_config_path()
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
            "embedding": embedding,
        }

    except ValueError as ve:
        # ✅ Clean user error (no 500)
        raise HTTPException(status_code=400, detail=str(ve))

    except (AssertionError, RuntimeError) as svc_exc:
        log_exception(
            logger,
            "Embedding model/service failure",
            extra={
                "person_id": person_id,
                "name": name,
                "filename": file.filename,
            },
            exc=svc_exc,
        )
        raise HTTPException(
            status_code=503,
            detail=f"Embedding service unavailable: {str(svc_exc) or svc_exc.__class__.__name__}",
        )

    except Exception as exc:
        # ✅ Log full traceback properly
        log_exception(
            logger,
            "Embedding failed",
            extra={
                "person_id": person_id,
                "name": name,
                "filename": file.filename,
            },
            exc=exc,
        )

        msg = str(exc) or exc.__class__.__name__
        raise HTTPException(
            status_code=503,
            detail=f"Embedding service error: {msg}",
        )

    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception as cleanup_exc:
            log_exception(
                logger,
                "Failed to cleanup temp embedding file",
                extra={"path": str(temp_path)},
                exc=cleanup_exc,
            )
