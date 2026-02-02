from __future__ import annotations

from sqlalchemy import Column, BigInteger, Text, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

from . import Base


class AnprEvent(Base):
    __tablename__ = "anpr_events"

    id = Column(BigInteger, primary_key=True, index=True)
    event_id = Column(UUID(as_uuid=True), unique=True, nullable=True)

    godown_id = Column(Text, nullable=False, index=True)
    camera_id = Column(Text, nullable=False, index=True)
    zone_id = Column(Text, nullable=True)

    timestamp_utc = Column(DateTime(timezone=True), nullable=False, index=True)

    plate_raw = Column(Text, nullable=True)
    plate_norm = Column(Text, nullable=True, index=True)

    match_status = Column(Text, nullable=False, default="UNKNOWN", index=True)
    event_type = Column(Text, nullable=False, index=True)

    det_conf = Column(Float, nullable=True)
    ocr_conf = Column(Float, nullable=True)
    combined_conf = Column(Float, nullable=True)

    bbox = Column(JSONB, nullable=True)
    snapshot_url = Column(Text, nullable=True)
    meta = Column(JSONB, nullable=False, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
