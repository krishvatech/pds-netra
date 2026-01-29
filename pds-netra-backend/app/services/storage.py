"""
Storage abstraction for watchlist images.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class StorageResult:
    storage_path: str
    public_url: Optional[str]


class StorageProvider:
    def save_bytes(self, *, data: bytes, content_type: Optional[str], filename_hint: Optional[str]) -> StorageResult:
        raise NotImplementedError


class LocalStorageProvider(StorageProvider):
    def __init__(self) -> None:
        base_dir = os.getenv("WATCHLIST_STORAGE_DIR")
        if base_dir:
            self.root = Path(base_dir).expanduser()
        else:
            self.root = Path(__file__).resolve().parents[2] / "data" / "watchlist"
        self.root.mkdir(parents=True, exist_ok=True)
        self.base_url = os.getenv("WATCHLIST_IMAGE_BASE_URL")

    def save_bytes(self, *, data: bytes, content_type: Optional[str], filename_hint: Optional[str]) -> StorageResult:
        ext = ".jpg"
        if filename_hint and "." in filename_hint:
            ext = "." + filename_hint.split(".")[-1].lower()
            if len(ext) > 6:
                ext = ".jpg"
        filename = f"{uuid.uuid4().hex}{ext}"
        out_path = self.root / filename
        out_path.write_bytes(data)
        public_url = None
        if self.base_url:
            public_url = self.base_url.rstrip("/") + "/" + filename
        return StorageResult(storage_path=str(out_path), public_url=public_url)


class S3StorageProvider(StorageProvider):
    def __init__(self) -> None:
        try:
            import boto3  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("boto3 is required for WATCHLIST_STORAGE_BACKEND=s3") from exc
        self._boto3 = boto3
        self.bucket = os.getenv("WATCHLIST_S3_BUCKET", "")
        self.endpoint_url = os.getenv("WATCHLIST_S3_ENDPOINT")
        self.region = os.getenv("WATCHLIST_S3_REGION")
        self.access_key = os.getenv("WATCHLIST_S3_ACCESS_KEY")
        self.secret_key = os.getenv("WATCHLIST_S3_SECRET_KEY")
        self.public_url = os.getenv("WATCHLIST_S3_PUBLIC_URL")
        if not self.bucket:
            raise RuntimeError("WATCHLIST_S3_BUCKET is required for s3 storage")
        self.client = self._boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )

    def save_bytes(self, *, data: bytes, content_type: Optional[str], filename_hint: Optional[str]) -> StorageResult:
        ext = ".jpg"
        if filename_hint and "." in filename_hint:
            ext = "." + filename_hint.split(".")[-1].lower()
            if len(ext) > 6:
                ext = ".jpg"
        key = f"watchlist/{uuid.uuid4().hex}{ext}"
        extra = {}
        if content_type:
            extra["ContentType"] = content_type
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, **extra)
        public_url = None
        if self.public_url:
            public_url = self.public_url.rstrip("/") + "/" + key
        return StorageResult(storage_path=key, public_url=public_url)


def get_storage_provider() -> StorageProvider:
    backend = os.getenv("WATCHLIST_STORAGE_BACKEND", "local").lower()
    if backend == "s3":
        return S3StorageProvider()
    return LocalStorageProvider()
