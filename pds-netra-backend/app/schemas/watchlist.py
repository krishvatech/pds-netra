"""
Pydantic schemas for watchlist and face match events.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


class WatchlistPersonImageOut(BaseModel):
    id: str
    image_url: Optional[str] = None
    storage_path: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class WatchlistPersonEmbeddingOut(BaseModel):
    id: str
    embedding_version: str
    embedding_hash: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class WatchlistPersonOut(BaseModel):
    id: str
    name: str
    alias: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    images: List[WatchlistPersonImageOut] = []
    embeddings: List[WatchlistPersonEmbeddingOut] = []

    model_config = ConfigDict(from_attributes=True)


class WatchlistPersonCreate(BaseModel):
    name: str
    alias: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None


class WatchlistPersonUpdate(BaseModel):
    name: Optional[str] = None
    alias: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class WatchlistEmbeddingIn(BaseModel):
    embedding: List[float]
    embedding_version: str = "v1"
    embedding_hash: Optional[str] = None


class WatchlistEmbeddingsCreate(BaseModel):
    embeddings: List[WatchlistEmbeddingIn]


class FaceMatchCandidate(BaseModel):
    embedding_hash: Optional[str] = None
    match_score: float
    is_blacklisted: bool
    blacklist_person_id: Optional[str] = None


class FaceMatchEvidence(BaseModel):
    snapshot_url: Optional[str] = None
    local_snapshot_path: Optional[str] = None
    bbox: Optional[List[int]] = None
    frame_ts: Optional[str] = None


class FaceMatchPayload(BaseModel):
    person_candidate: FaceMatchCandidate
    evidence: FaceMatchEvidence


class FaceMatchEventIn(BaseModel):
    schema_version: str = Field("1.0")
    event_id: str
    occurred_at: datetime
    godown_id: str
    camera_id: str
    stream_id: Optional[str] = None
    event_type: str = Field("FACE_MATCH")
    payload: FaceMatchPayload
    correlation_id: Optional[str] = None


class FaceMatchEventOut(BaseModel):
    id: str
    occurred_at: datetime
    godown_id: str
    camera_id: str
    stream_id: Optional[str] = None
    match_score: float
    is_blacklisted: bool
    blacklist_person_id: Optional[str] = None
    snapshot_url: Optional[str] = None
    storage_path: Optional[str] = None
    correlation_id: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class WatchlistSyncPerson(BaseModel):
    id: str
    name: str
    alias: Optional[str] = None
    reason: Optional[str] = None
    status: str
    updated_at: Optional[datetime] = None
    images: List[WatchlistPersonImageOut] = []
    embeddings: List[WatchlistEmbeddingIn] = []


class WatchlistSyncResponse(BaseModel):
    schema_version: str = Field("1.0")
    checksum: str
    generated_at: datetime
    items: List[WatchlistSyncPerson]
