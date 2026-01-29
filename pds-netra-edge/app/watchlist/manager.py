"""
Watchlist sync manager for edge nodes.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.request
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import numpy as np  # type: ignore
except ImportError:
    np = None  # type: ignore

try:
    import faiss  # type: ignore
    _FAISS_OK = True
except Exception:
    faiss = None  # type: ignore
    _FAISS_OK = False

try:
    import cv2  # type: ignore
except Exception:
    cv2 = None  # type: ignore

from ..cv.face_id import detect_faces


@dataclass
class WatchlistEntry:
    person_id: str
    name: str
    alias: Optional[str]
    reason: Optional[str]
    embeddings: List[List[float]]
    embedding_hashes: List[str]


class WatchlistIndex:
    def __init__(self, dim: int = 512) -> None:
        self.dim = dim
        self.ids: List[int] = []
        self.index = None
        self._mat = None
        if _FAISS_OK:
            self.index = faiss.IndexFlatIP(self.dim)  # type: ignore[attr-defined]

    def build(self, embeddings: "np.ndarray", ids: List[int]) -> None:
        if np is None or embeddings.size == 0:
            self.ids = []
            self._mat = None
            if _FAISS_OK:
                self.index = faiss.IndexFlatIP(self.dim)  # type: ignore[attr-defined]
            return
        embeddings = embeddings.astype("float32")
        self.dim = int(embeddings.shape[1])
        self.ids = list(ids)
        if _FAISS_OK:
            self.index = faiss.IndexFlatIP(self.dim)  # type: ignore[attr-defined]
            self.index.add(embeddings)
        else:
            self._mat = embeddings

    def ready(self) -> bool:
        return bool(self.ids)

    def query(self, embedding: "np.ndarray", k: int = 1) -> Optional[Tuple[int, float]]:
        if np is None or not self.ready():
            return None
        vec = embedding.astype("float32").reshape(1, -1)
        if _FAISS_OK and self.index is not None:
            scores, idx = self.index.search(vec, k)
            if idx.size == 0:
                return None
            match_idx = int(idx[0][0])
            if match_idx < 0 or match_idx >= len(self.ids):
                return None
            return self.ids[match_idx], float(scores[0][0])
        if self._mat is None:
            return None
        scores = vec @ self._mat.T
        match_idx = int(scores.argmax())
        return self.ids[match_idx], float(scores[0][match_idx])


class WatchlistManager:
    def __init__(
        self,
        *,
        backend_url: str,
        cache_dir: Path,
        sync_interval_sec: int = 300,
        auto_embed: bool = False,
        auth_token: Optional[str] = None,
    ) -> None:
        self.logger = logging.getLogger("watchlist")
        self.backend_url = backend_url.rstrip("/")
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.cache_dir / "watchlist_cache.json"
        self.sync_interval_sec = max(30, int(sync_interval_sec))
        self.auto_embed = auto_embed
        self.auth_token = auth_token
        self._checksum: Optional[str] = None
        self._entries: List[WatchlistEntry] = []
        self._index = WatchlistIndex()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._load_cached()

    def _load_cached(self) -> None:
        if not self.cache_path.exists():
            return
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception:
            return
        checksum = payload.get("checksum")
        items = payload.get("items") if isinstance(payload, dict) else []
        entries, embeddings, ids = self._build_entries(items if isinstance(items, list) else [])
        with self._lock:
            self._entries = entries
            if np is not None and embeddings:
                mat = np.vstack(embeddings).astype("float32")
                self._index.build(mat, ids)
            elif np is not None:
                self._index.build(np.zeros((0, 0), dtype="float32"), [])
            else:
                self._index.ids = []
            self._checksum = checksum

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name="WatchlistSync", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.sync_once()
            except Exception as exc:
                self.logger.warning("Watchlist sync failed: %s", exc)
            self._stop_event.wait(timeout=self.sync_interval_sec)

    def sync_once(self) -> None:
        url = f"{self.backend_url}/api/v1/watchlist/sync"
        payload = self._http_get_json(url)
        if not isinstance(payload, dict):
            return
        checksum = payload.get("checksum")
        if checksum and checksum == self._checksum:
            return
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        entries, embeddings, ids = self._build_entries(items)
        with self._lock:
            self._entries = entries
            if np is not None and embeddings:
                mat = np.vstack(embeddings).astype("float32")
                self._index.build(mat, ids)
            else:
                if np is not None:
                    self._index.build(np.zeros((0, 0), dtype="float32"), [])
                else:
                    self._index.ids = []
            self._checksum = checksum
        self.cache_path.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
        if self.auto_embed:
            self._auto_generate_embeddings(items)
        self.logger.info("Watchlist synced: %s entries", len(entries))

    def _http_get_json(self, url: str) -> Optional[dict]:
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
            headers["X-User-Role"] = "STATE_ADMIN"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            self.logger.warning("Watchlist sync request failed: %s", exc)
            return None

    def _build_entries(self, items: list) -> Tuple[List[WatchlistEntry], List["np.ndarray"], List[int]]:
        entries: List[WatchlistEntry] = []
        embeddings: List["np.ndarray"] = []
        ids: List[int] = []
        if np is None:
            return entries, embeddings, ids
        for idx, item in enumerate(items):
            person_id = str(item.get("id"))
            name = str(item.get("name") or "")
            alias = item.get("alias")
            reason = item.get("reason")
            raw_embeddings = item.get("embeddings") or []
            vectors: List[List[float]] = []
            hashes: List[str] = []
            for emb in raw_embeddings:
                vec = emb.get("embedding") if isinstance(emb, dict) else None
                if not isinstance(vec, list):
                    continue
                vectors.append([float(x) for x in vec])
                hash_val = emb.get("embedding_hash") if isinstance(emb, dict) else None
                hashes.append(str(hash_val) if hash_val else self._hash_embedding(vec))
            entries.append(WatchlistEntry(person_id=person_id, name=name, alias=alias, reason=reason, embeddings=vectors, embedding_hashes=hashes))
            for vec in vectors:
                embeddings.append(np.array(vec, dtype="float32"))
                ids.append(idx)
        return entries, embeddings, ids

    def _hash_embedding(self, vec: List[float]) -> str:
        payload = ",".join(f"{v:.6f}" for v in vec)
        return sha256(payload.encode("utf-8")).hexdigest()[:24]

    def _auto_generate_embeddings(self, items: list) -> None:
        if np is None or cv2 is None:
            return
        for item in items:
            person_id = str(item.get("id"))
            embeddings = item.get("embeddings") or []
            if embeddings:
                continue
            images = item.get("images") or []
            if not images:
                continue
            for image in images:
                img = self._load_image(image)
                if img is None:
                    continue
                faces = detect_faces(img)
                if not faces:
                    continue
                _, embedding = faces[0]
                if embedding:
                    emb_hash = self._hash_embedding(embedding)
                    self._post_embedding(person_id, embedding, emb_hash)
                break

    def _load_image(self, image: dict) -> Optional["np.ndarray"]:
        if cv2 is None or np is None:
            return None
        source = image.get("image_url") or image.get("storage_path")
        if not source:
            return None
        if isinstance(source, str) and source.startswith("http"):
            try:
                with urllib.request.urlopen(source, timeout=5) as resp:
                    data = resp.read()
                arr = np.frombuffer(data, dtype=np.uint8)
                return cv2.imdecode(arr, cv2.IMREAD_COLOR)
            except Exception:
                return None
        path = Path(str(source))
        if not path.is_absolute():
            base = os.getenv("EDGE_WATCHLIST_STORAGE_ROOT")
            if base:
                path = Path(base).expanduser() / path
        if path.exists():
            return cv2.imread(str(path))
        return None

    def _post_embedding(self, person_id: str, embedding: List[float], emb_hash: str) -> None:
        url = f"{self.backend_url}/api/v1/watchlist/persons/{person_id}/embeddings"
        payload = {
            "embeddings": [
                {
                    "embedding": embedding,
                    "embedding_version": "v1",
                    "embedding_hash": emb_hash,
                }
            ]
        }
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
            headers["X-User-Role"] = "STATE_ADMIN"
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5):
                pass
            self.logger.info("Uploaded embedding for %s", person_id)
        except Exception as exc:
            self.logger.warning("Failed to upload embedding for %s: %s", person_id, exc)

    def match(self, embedding: List[float]) -> Optional[Tuple[WatchlistEntry, float, str]]:
        if np is None:
            return None
        with self._lock:
            if not self._index.ready():
                return None
            try:
                candidate = np.array(embedding, dtype="float32")
            except Exception:
                return None
            result = self._index.query(candidate, k=1)
            if result is None:
                return None
            entry_idx, score = result
            if entry_idx < 0 or entry_idx >= len(self._entries):
                return None
            entry = self._entries[entry_idx]
            emb_hash = entry.embedding_hashes[0] if entry.embedding_hashes else ""
            return entry, float(score), emb_hash
