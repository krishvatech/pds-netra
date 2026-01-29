"""
Shared watchlist and face match contracts for edge publishing.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


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


class FaceMatchEvent(BaseModel):
    schema_version: str = Field("1.0")
    event_id: str
    occurred_at: str
    godown_id: str
    camera_id: str
    stream_id: Optional[str] = None
    event_type: str = Field("FACE_MATCH")
    payload: FaceMatchPayload
    correlation_id: Optional[str] = None
