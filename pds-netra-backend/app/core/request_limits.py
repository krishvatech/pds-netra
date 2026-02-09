"""Request size limits for JSON bodies and uploads."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import HTTPException, Request, UploadFile


def _max_json_body_bytes() -> int:
    raw = os.getenv("MAX_JSON_BODY_BYTES", "1048576")
    try:
        val = int(raw)
    except Exception:
        val = 1048576
    return max(val, 1024)


def _max_upload_bytes() -> int:
    raw = os.getenv("MAX_UPLOAD_BYTES", "10485760")
    try:
        val = int(raw)
    except Exception:
        val = 10485760
    return max(val, 1024)


def _content_length_too_large(request: Request, max_bytes: int) -> bool:
    length = request.headers.get("content-length")
    if not length:
        return False
    try:
        return int(length) > max_bytes
    except Exception:
        return False


async def enforce_json_body_limit(request: Request) -> None:
    max_bytes = _max_json_body_bytes()
    if _content_length_too_large(request, max_bytes):
        raise HTTPException(status_code=413, detail="Payload too large")
    # Best-effort fallback when Content-Length is missing.
    if "content-length" not in {k.lower() for k in request.headers.keys()}:
        body = await request.body()
        if len(body) > max_bytes:
            raise HTTPException(status_code=413, detail="Payload too large")


def enforce_upload_limit(request: Request) -> None:
    max_bytes = _max_upload_bytes()
    if _content_length_too_large(request, max_bytes):
        raise HTTPException(status_code=413, detail="Payload too large")


def read_upload_bytes_sync(upload: UploadFile, *, max_bytes: Optional[int] = None) -> bytes:
    limit = max_bytes or _max_upload_bytes()
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail="Upload too large")
    return data


async def read_upload_bytes_async(upload: UploadFile, *, max_bytes: Optional[int] = None) -> bytes:
    limit = max_bytes or _max_upload_bytes()
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail="Upload too large")
    return data


def copy_upload_file(upload: UploadFile, dest, *, max_bytes: Optional[int] = None) -> int:
    limit = max_bytes or _max_upload_bytes()
    copied = 0
    while True:
        chunk = upload.file.read(1024 * 1024)
        if not chunk:
            break
        copied += len(chunk)
        if copied > limit:
            raise HTTPException(status_code=413, detail="Upload too large")
        dest.write(chunk)
    return copied
