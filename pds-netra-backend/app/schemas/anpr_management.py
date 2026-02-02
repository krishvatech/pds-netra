"""
Pydantic schemas for ANPR vehicle registry and daily plans.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class AnprVehicleOut(BaseModel):
    id: str
    godown_id: str
    plate_raw: str
    plate_norm: str
    list_type: Optional[str] = "WHITELIST"
    transporter: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AnprVehicleCreate(BaseModel):
    godown_id: str
    plate_text: str = Field(..., description="Raw plate text; normalized server-side.")
    list_type: Optional[str] = "WHITELIST"
    transporter: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True


class AnprVehicleUpdate(BaseModel):
    plate_text: Optional[str] = None
    list_type: Optional[str] = None
    transporter: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class DailyPlanOut(BaseModel):
    id: str
    godown_id: str
    plan_date: date
    timezone_name: str
    expected_count: Optional[int] = None
    cutoff_time_local: time
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DailyPlanUpsert(BaseModel):
    godown_id: str
    plan_date: date
    timezone_name: str = "Asia/Kolkata"
    expected_count: Optional[int] = None
    cutoff_time_local: Optional[time] = None
    notes: Optional[str] = None


class DailyPlanItemOut(BaseModel):
    id: str
    plan_id: str
    vehicle_id: Optional[str] = None
    plate_raw: str
    plate_norm: str
    expected_by_local: Optional[time] = None
    status: Optional[str] = None
    notes: Optional[str] = None

    # computed (not stored)
    effective_status: str = "PLANNED"
    arrived_at_utc: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DailyPlanItemCreate(BaseModel):
    plan_id: str
    vehicle_id: Optional[str] = None
    plate_text: Optional[str] = None
    expected_by_local: Optional[time] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class DailyPlanItemUpdate(BaseModel):
    expected_by_local: Optional[time] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class DailyReportRow(BaseModel):
    date_local: date
    expected_count: Optional[int] = None
    planned_items: int = 0
    arrived: int = 0
    delayed: int = 0
    no_show: int = 0
    cancelled: int = 0


class DailyReportOut(BaseModel):
    godown_id: str
    timezone_name: str
    rows: List[DailyReportRow]


class CsvImportRowResult(BaseModel):
    row_number: int
    plate_text: str
    status: str
    message: Optional[str] = None
    entity_id: Optional[str] = None


class CsvImportSummary(BaseModel):
    total: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    rows: List[CsvImportRowResult] = []
