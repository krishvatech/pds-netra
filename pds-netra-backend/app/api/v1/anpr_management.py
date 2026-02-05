"""
ANPR management endpoints:
- Vehicle registry (per godown)
- Daily arrival plans (date-wise expected vehicles + statuses)
- Simple daily report generation
"""

from __future__ import annotations

import csv
import datetime
import io
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from ...core.auth import get_optional_user
from ...core.db import get_db
from ...models.anpr_vehicle import AnprVehicle
from ...models.anpr_event import AnprEvent
from ...models.anpr_daily_plan import AnprDailyPlan
from ...models.anpr_daily_plan_item import AnprDailyPlanItem
from ...schemas.anpr_management import (
    AnprVehicleCreate,
    AnprVehicleOut,
    AnprVehicleUpdate,
    DailyPlanItemCreate,
    DailyPlanItemOut,
    DailyPlanItemUpdate,
    DailyPlanOut,
    DailyPlanUpsert,
    DailyReportOut,
    DailyReportRow,
    CsvImportSummary,
    CsvImportRowResult,
)

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None


router = APIRouter(prefix="/api/v1/anpr", tags=["anpr"])


PLAN_STATUSES = {"PLANNED", "ARRIVED", "DELAYED", "CANCELLED", "NO_SHOW"}
LIST_TYPES = {"WHITELIST", "BLACKLIST"}
ANPR_EVENT_TYPES = (
    "ANPR_PLATE_VERIFIED",
    "ANPR_PLATE_ALERT",
    "ANPR_PLATE_DETECTED",
    "ANPR_TIME_VIOLATION",
)


def _normalize_plate(text: str) -> str:
    return "".join(ch for ch in (text or "").upper() if ch.isalnum())


def _coerce_status(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = str(value).strip().upper()
    if not v:
        return None
    if v not in PLAN_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {v}")
    return v


def _coerce_list_type(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = str(value).strip().upper()
    if not v:
        return None
    if v not in LIST_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid list_type: {v}")
    return v


def _coerce_bool(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    v = str(value).strip().lower()
    if not v:
        return None
    if v in {"1", "true", "yes", "y"}:
        return True
    if v in {"0", "false", "no", "n"}:
        return False
    raise HTTPException(status_code=400, detail=f"Invalid boolean: {value}")


def _parse_time(value: Optional[str]) -> Optional[datetime.time]:
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    try:
        return datetime.time.fromisoformat(v)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid time: {value}")


def _read_csv_rows(upload: UploadFile) -> list[dict[str, str]]:
    raw = upload.file.read()
    if not raw:
        return []
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []
    rows: list[dict[str, str]] = []
    for row in reader:
        if not row:
            continue
        rows.append({(k or "").strip(): (v or "").strip() for k, v in row.items()})
    return rows


def _local_day_range_to_utc(tz_name: str, d: datetime.date) -> tuple[datetime.datetime, datetime.datetime]:
    tz = ZoneInfo(tz_name) if ZoneInfo else datetime.timezone.utc
    start_local = datetime.datetime.combine(d, datetime.time.min).replace(tzinfo=tz)
    end_local = start_local + datetime.timedelta(days=1)
    return start_local.astimezone(datetime.timezone.utc), end_local.astimezone(datetime.timezone.utc)


def _verified_arrivals_for_range(
    db: Session,
    *,
    godown_id: str,
    start_utc: datetime.datetime,
    end_utc: datetime.datetime,
) -> tuple[dict[str, datetime.datetime], set[str]]:
    rows = (
        db.query(
            AnprEvent.plate_norm,
            AnprEvent.plate_raw,
            AnprEvent.match_status,
            AnprEvent.timestamp_utc,
        )
        .filter(
            AnprEvent.godown_id == godown_id,
            AnprEvent.timestamp_utc >= start_utc,
            AnprEvent.timestamp_utc < end_utc,
            AnprEvent.event_type.in_(ANPR_EVENT_TYPES),
        )
        .all()
    )
    plate_norms = {pn for (pn, _, _, _) in rows if pn}
    registry: dict[str, str] = {}
    if plate_norms:
        regs = (
            db.query(AnprVehicle.plate_norm, AnprVehicle.list_type)
            .filter(
                AnprVehicle.godown_id == godown_id,
                AnprVehicle.plate_norm.in_(plate_norms),
                AnprVehicle.is_active == True,  # noqa: E712
            )
            .all()
        )
        registry = {pn: (lt or "WHITELIST").upper() for pn, lt in regs}

    arrived_at: dict[str, datetime.datetime] = {}
    for pn, raw, status, ts in rows:
        plate = pn or _normalize_plate(raw or "")
        if not plate:
            continue
        s = (status or "UNKNOWN").upper()
        if s not in {"VERIFIED", "BLACKLIST"} and plate in registry:
            s = "BLACKLIST" if registry[plate] == "BLACKLIST" else "VERIFIED"
        if s not in {"VERIFIED", "BLACKLIST"}:
            continue
        prev = arrived_at.get(plate)
        if prev is None or ts < prev:
            arrived_at[plate] = ts
    return arrived_at, set(arrived_at.keys())


def _enforce_godown_scope(user, godown_id: str) -> str:
    if user and user.role.upper() == "GODOWN_MANAGER" and user.godown_id:
        if godown_id != user.godown_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user.godown_id
    return godown_id


# -------------------------
# Vehicles
# -------------------------
@router.get("/vehicles")
def list_anpr_vehicles(
    godown_id: str = Query(...),
    q: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
) -> dict:
    godown_id = _enforce_godown_scope(user, godown_id)
    query = db.query(AnprVehicle).filter(AnprVehicle.godown_id == godown_id)
    if is_active is not None:
        query = query.filter(AnprVehicle.is_active == bool(is_active))
    if q:
        term = _normalize_plate(q)
        if term:
            query = query.filter(func.upper(AnprVehicle.plate_norm).like(f"%{term}%"))
        else:
            query = query.filter(func.upper(AnprVehicle.plate_raw).like(f"%{q.strip().upper()}%"))

    total = query.count()
    items = (
        query.order_by(AnprVehicle.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    out = [AnprVehicleOut.model_validate(v).model_dump() for v in items]
    return {"items": out, "total": total, "page": page, "page_size": page_size}


@router.post("/vehicles", response_model=AnprVehicleOut)
def create_anpr_vehicle(
    payload: AnprVehicleCreate,
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
) -> AnprVehicleOut:
    godown_id = _enforce_godown_scope(user, payload.godown_id)
    plate_raw = payload.plate_text.strip()
    plate_norm = _normalize_plate(plate_raw)
    if not plate_norm:
        raise HTTPException(status_code=400, detail="Invalid plate_text")

    existing = (
        db.query(AnprVehicle)
        .filter(AnprVehicle.godown_id == godown_id, AnprVehicle.plate_norm == plate_norm)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Vehicle already exists for this godown")

    v = AnprVehicle(
        godown_id=godown_id,
        plate_raw=plate_raw,
        plate_norm=plate_norm,
        list_type=_coerce_list_type(payload.list_type) or "WHITELIST",
        transporter=payload.transporter,
        notes=payload.notes,
        is_active=bool(payload.is_active),
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return AnprVehicleOut.model_validate(v)


@router.put("/vehicles/{vehicle_id}", response_model=AnprVehicleOut)
def update_anpr_vehicle(
    vehicle_id: str,
    payload: AnprVehicleUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
) -> AnprVehicleOut:
    v = db.get(AnprVehicle, vehicle_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    _enforce_godown_scope(user, v.godown_id)

    data = payload.model_dump(exclude_unset=True)

    if "plate_text" in data:
        plate_raw = (data.get("plate_text") or "").strip()
        plate_norm = _normalize_plate(plate_raw)
        if not plate_norm:
            raise HTTPException(status_code=400, detail="Invalid plate_text")
        # uniqueness per godown
        dup = (
            db.query(AnprVehicle)
            .filter(AnprVehicle.godown_id == v.godown_id, AnprVehicle.plate_norm == plate_norm, AnprVehicle.id != v.id)
            .first()
        )
        if dup:
            raise HTTPException(status_code=409, detail="Another vehicle already uses this plate")
        v.plate_raw = plate_raw
        v.plate_norm = plate_norm

    if "transporter" in data:
        v.transporter = data.get("transporter")
    if "notes" in data:
        v.notes = data.get("notes")
    if "list_type" in data:
        v.list_type = _coerce_list_type(data.get("list_type")) or v.list_type
    if "is_active" in data:
        val = data.get("is_active")
        if val is not None:
            v.is_active = bool(val)

    db.add(v)
    db.commit()
    db.refresh(v)
    return AnprVehicleOut.model_validate(v)


@router.delete("/vehicles/{vehicle_id}")
def delete_anpr_vehicle(
    vehicle_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
) -> dict:
    v = db.get(AnprVehicle, vehicle_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    _enforce_godown_scope(user, v.godown_id)

    # Unlink any daily plan items that referenced this vehicle.
    linked_items = (
        db.query(AnprDailyPlanItem)
        .filter(AnprDailyPlanItem.vehicle_id == vehicle_id)
        .all()
    )
    for item in linked_items:
        item.vehicle_id = None
        db.add(item)

    db.delete(v)
    db.commit()
    return {"status": "deleted", "id": vehicle_id, "unlinked_plan_items": len(linked_items)}


@router.post("/vehicles/import", response_model=CsvImportSummary)
def import_anpr_vehicles_csv(
    godown_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
) -> CsvImportSummary:
    godown_id = _enforce_godown_scope(user, godown_id)
    rows = _read_csv_rows(file)
    summary = CsvImportSummary(total=len(rows))
    if not rows:
        return summary

    for row_number, row in enumerate(rows, start=2):
        lower = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
        plate_text = lower.get("plate_text") or lower.get("plate") or lower.get("plate_no") or lower.get("plate_number")
        if not plate_text:
            summary.failed += 1
            summary.rows.append(
                CsvImportRowResult(row_number=row_number, plate_text="", status="failed", message="plate_text is required")
            )
            continue
        plate_raw = plate_text.strip()
        plate_norm = _normalize_plate(plate_raw)
        if not plate_norm:
            summary.failed += 1
            summary.rows.append(
                CsvImportRowResult(row_number=row_number, plate_text=plate_raw, status="failed", message="Invalid plate")
            )
            continue

        try:
            existing = (
                db.query(AnprVehicle)
                .filter(AnprVehicle.godown_id == godown_id, AnprVehicle.plate_norm == plate_norm)
                .first()
            )

            list_type = lower.get("list_type")
            transporter = lower.get("transporter")
            notes = lower.get("notes")
            is_active = lower.get("is_active")

            if existing:
                if plate_raw:
                    existing.plate_raw = plate_raw
                if "list_type" in lower and list_type:
                    existing.list_type = _coerce_list_type(list_type) or existing.list_type
                if "transporter" in lower:
                    existing.transporter = transporter or None
                if "notes" in lower:
                    existing.notes = notes or None
                if "is_active" in lower:
                    val = _coerce_bool(is_active)
                    if val is not None:
                        existing.is_active = bool(val)
                db.add(existing)
                summary.updated += 1
                summary.rows.append(
                    CsvImportRowResult(
                        row_number=row_number,
                        plate_text=plate_raw,
                        status="updated",
                        entity_id=existing.id,
                    )
                )
            else:
                list_type_value = _coerce_list_type(list_type) if list_type else "WHITELIST"
                active_val = _coerce_bool(is_active)
                v = AnprVehicle(
                    godown_id=godown_id,
                    plate_raw=plate_raw,
                    plate_norm=plate_norm,
                    list_type=list_type_value or "WHITELIST",
                    transporter=transporter or None,
                    notes=notes or None,
                    is_active=bool(active_val) if active_val is not None else True,
                )
                db.add(v)
                summary.created += 1
                summary.rows.append(
                    CsvImportRowResult(row_number=row_number, plate_text=plate_raw, status="created")
                )
        except HTTPException as exc:
            summary.failed += 1
            summary.rows.append(
                CsvImportRowResult(
                    row_number=row_number,
                    plate_text=plate_raw,
                    status="failed",
                    message=str(exc.detail),
                )
            )

    db.commit()
    return summary


# -------------------------
# Daily Plans
# -------------------------
@router.get("/daily-plan")
def get_daily_plan(
    godown_id: str = Query(...),
    date_local: datetime.date = Query(..., alias="date"),
    timezone_name: str = Query("Asia/Kolkata"),
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
) -> dict:
    godown_id = _enforce_godown_scope(user, godown_id)

    plan = (
        db.query(AnprDailyPlan)
        .filter(AnprDailyPlan.godown_id == godown_id, AnprDailyPlan.plan_date == date_local)
        .first()
    )
    if plan is None:
        plan = AnprDailyPlan(
            godown_id=godown_id,
            plan_date=date_local,
            timezone_name=timezone_name,
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)

    tz_name = plan.timezone_name or timezone_name
    start_utc, end_utc = _local_day_range_to_utc(tz_name, plan.plan_date)

    arrived_at, arrived_set = _verified_arrivals_for_range(
        db,
        godown_id=godown_id,
        start_utc=start_utc,
        end_utc=end_utc,
    )

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    tz = ZoneInfo(tz_name) if ZoneInfo else datetime.timezone.utc
    now_local = now_utc.astimezone(tz)
    today_local = now_local.date()

    def effective(item: AnprDailyPlanItem) -> tuple[str, Optional[str]]:
        manual = _coerce_status(item.status) if item.status else None
        pn = item.plate_norm
        if manual == "CANCELLED":
            return "CANCELLED", None
        if pn in arrived_at:
            return "ARRIVED", arrived_at[pn].astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        # Not arrived
        if plan.plan_date < today_local:
            return ("NO_SHOW" if manual in (None, "PLANNED", "DELAYED") else manual), None
        if plan.plan_date > today_local:
            return (manual or "PLANNED"), None
        # today
        cutoff = plan.cutoff_time_local or datetime.time(18, 0)
        if now_local.time() >= cutoff:
            return ("NO_SHOW" if manual in (None, "PLANNED", "DELAYED") else manual), None
        if item.expected_by_local and now_local.time() >= item.expected_by_local:
            return ("DELAYED" if manual in (None, "PLANNED") else manual), None
        return (manual or "PLANNED"), None

    items_out: list[dict] = []
    for it in sorted(plan.items or [], key=lambda x: (x.expected_by_local or datetime.time.min, x.plate_norm)):
        eff, arrived_iso = effective(it)
        dto = DailyPlanItemOut.model_validate(it).model_dump()
        dto["effective_status"] = eff
        dto["arrived_at_utc"] = arrived_iso
        items_out.append(dto)

    return {
        "plan": DailyPlanOut.model_validate(plan).model_dump(),
        "items": items_out,
    }


@router.put("/daily-plan", response_model=DailyPlanOut)
def upsert_daily_plan(
    payload: DailyPlanUpsert,
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
) -> DailyPlanOut:
    data = payload.model_dump(exclude_unset=True)
    godown_id = _enforce_godown_scope(user, payload.godown_id)
    plan = (
        db.query(AnprDailyPlan)
        .filter(AnprDailyPlan.godown_id == godown_id, AnprDailyPlan.plan_date == payload.plan_date)
        .first()
    )
    if plan is None:
        plan = AnprDailyPlan(
            godown_id=godown_id,
            plan_date=payload.plan_date,
            timezone_name=payload.timezone_name,
        )
    plan.timezone_name = payload.timezone_name or plan.timezone_name
    if "expected_count" in data:
        plan.expected_count = data.get("expected_count")
    if "cutoff_time_local" in data:
        plan.cutoff_time_local = data.get("cutoff_time_local") or plan.cutoff_time_local
    if "notes" in data:
        plan.notes = data.get("notes")

    db.add(plan)
    db.commit()
    db.refresh(plan)
    return DailyPlanOut.model_validate(plan)


@router.post("/daily-plan/items", response_model=DailyPlanItemOut)
def add_daily_plan_item(
    payload: DailyPlanItemCreate,
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
) -> DailyPlanItemOut:
    plan = db.get(AnprDailyPlan, payload.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    _enforce_godown_scope(user, plan.godown_id)

    vehicle = None
    plate_raw = ""
    plate_norm = ""
    if payload.vehicle_id:
        vehicle = db.get(AnprVehicle, payload.vehicle_id)
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        if vehicle.godown_id != plan.godown_id:
            raise HTTPException(status_code=400, detail="Vehicle godown mismatch")
        plate_raw = vehicle.plate_raw
        plate_norm = vehicle.plate_norm
    else:
        if not payload.plate_text:
            raise HTTPException(status_code=400, detail="plate_text is required when vehicle_id is not provided")
        plate_raw = payload.plate_text.strip()
        plate_norm = _normalize_plate(plate_raw)

    if not plate_norm:
        raise HTTPException(status_code=400, detail="Invalid plate")

    exists = (
        db.query(AnprDailyPlanItem)
        .filter(AnprDailyPlanItem.plan_id == plan.id, AnprDailyPlanItem.plate_norm == plate_norm)
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail="Plate already exists in plan")

    it = AnprDailyPlanItem(
        plan_id=plan.id,
        vehicle_id=vehicle.id if vehicle else None,
        plate_raw=plate_raw,
        plate_norm=plate_norm,
        expected_by_local=payload.expected_by_local,
        status=_coerce_status(payload.status),
        notes=payload.notes,
    )
    db.add(it)
    db.commit()
    db.refresh(it)
    # effective status computed in GET; here return default
    dto = DailyPlanItemOut.model_validate(it)
    dto.effective_status = (dto.status or "PLANNED").upper()
    return dto


@router.post("/daily-plan/items/import", response_model=CsvImportSummary)
def import_daily_plan_items_csv(
    godown_id: str = Form(...),
    plan_date: datetime.date = Form(...),
    timezone_name: str = Form("Asia/Kolkata"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
) -> CsvImportSummary:
    godown_id = _enforce_godown_scope(user, godown_id)
    plan = (
        db.query(AnprDailyPlan)
        .filter(AnprDailyPlan.godown_id == godown_id, AnprDailyPlan.plan_date == plan_date)
        .first()
    )
    if plan is None:
        plan = AnprDailyPlan(
            godown_id=godown_id,
            plan_date=plan_date,
            timezone_name=timezone_name,
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)

    rows = _read_csv_rows(file)
    summary = CsvImportSummary(total=len(rows))
    if not rows:
        return summary

    for row_number, row in enumerate(rows, start=2):
        lower = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
        plate_text = lower.get("plate_text") or lower.get("plate") or lower.get("plate_no") or lower.get("plate_number")
        if not plate_text:
            summary.failed += 1
            summary.rows.append(
                CsvImportRowResult(row_number=row_number, plate_text="", status="failed", message="plate_text is required")
            )
            continue
        plate_raw = plate_text.strip()
        plate_norm = _normalize_plate(plate_raw)
        if not plate_norm:
            summary.failed += 1
            summary.rows.append(
                CsvImportRowResult(row_number=row_number, plate_text=plate_raw, status="failed", message="Invalid plate")
            )
            continue

        try:
            expected_by = _parse_time(lower.get("expected_by_local") or lower.get("expected_by"))
            status_value = lower.get("status")
            notes = lower.get("notes")

            existing = (
                db.query(AnprDailyPlanItem)
                .filter(AnprDailyPlanItem.plan_id == plan.id, AnprDailyPlanItem.plate_norm == plate_norm)
                .first()
            )

            vehicle = (
                db.query(AnprVehicle)
                .filter(AnprVehicle.godown_id == godown_id, AnprVehicle.plate_norm == plate_norm)
                .first()
            )

            if existing:
                if "expected_by_local" in lower or "expected_by" in lower:
                    existing.expected_by_local = expected_by
                if "status" in lower and status_value:
                    existing.status = _coerce_status(status_value)
                if "notes" in lower:
                    existing.notes = notes or None
                if vehicle and existing.vehicle_id != vehicle.id:
                    existing.vehicle_id = vehicle.id
                    existing.plate_raw = vehicle.plate_raw
                db.add(existing)
                summary.updated += 1
                summary.rows.append(
                    CsvImportRowResult(
                        row_number=row_number,
                        plate_text=plate_raw,
                        status="updated",
                        entity_id=existing.id,
                    )
                )
            else:
                it = AnprDailyPlanItem(
                    plan_id=plan.id,
                    vehicle_id=vehicle.id if vehicle else None,
                    plate_raw=vehicle.plate_raw if vehicle else plate_raw,
                    plate_norm=plate_norm,
                    expected_by_local=expected_by,
                    status=_coerce_status(status_value) if status_value else None,
                    notes=notes or None,
                )
                db.add(it)
                summary.created += 1
                summary.rows.append(
                    CsvImportRowResult(row_number=row_number, plate_text=plate_raw, status="created")
                )
        except HTTPException as exc:
            summary.failed += 1
            summary.rows.append(
                CsvImportRowResult(
                    row_number=row_number,
                    plate_text=plate_raw,
                    status="failed",
                    message=str(exc.detail),
                )
            )

    db.commit()
    return summary


@router.patch("/daily-plan/items/{item_id}", response_model=DailyPlanItemOut)
def update_daily_plan_item(
    item_id: str,
    payload: DailyPlanItemUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
) -> DailyPlanItemOut:
    it = db.get(AnprDailyPlanItem, item_id)
    if not it:
        raise HTTPException(status_code=404, detail="Item not found")
    plan = db.get(AnprDailyPlan, it.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    _enforce_godown_scope(user, plan.godown_id)

    data = payload.model_dump(exclude_unset=True)
    if "expected_by_local" in data:
        it.expected_by_local = data.get("expected_by_local")
    if "status" in data:
        it.status = _coerce_status(data.get("status"))
    if "notes" in data:
        it.notes = data.get("notes")

    db.add(it)
    db.commit()
    db.refresh(it)
    dto = DailyPlanItemOut.model_validate(it)
    dto.effective_status = (dto.status or "PLANNED").upper()
    return dto


@router.delete("/daily-plan/items/{item_id}")
def delete_daily_plan_item(
    item_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
) -> dict:
    it = db.get(AnprDailyPlanItem, item_id)
    if not it:
        raise HTTPException(status_code=404, detail="Item not found")
    plan = db.get(AnprDailyPlan, it.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    _enforce_godown_scope(user, plan.godown_id)

    db.delete(it)
    db.commit()
    return {"status": "deleted", "id": item_id}


# -------------------------
# Reports
# -------------------------
@router.get("/reports/daily", response_model=DailyReportOut)
def anpr_daily_report(
    godown_id: str = Query(...),
    timezone_name: str = Query("Asia/Kolkata"),
    date_from: datetime.date = Query(...),
    date_to: datetime.date = Query(...),
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
) -> DailyReportOut:
    godown_id = _enforce_godown_scope(user, godown_id)
    if date_to < date_from:
        raise HTTPException(status_code=400, detail="date_to must be >= date_from")

    plans = (
        db.query(AnprDailyPlan)
        .filter(
            AnprDailyPlan.godown_id == godown_id,
            AnprDailyPlan.plan_date >= date_from,
            AnprDailyPlan.plan_date <= date_to,
        )
        .all()
    )
    plan_by_date: dict[datetime.date, AnprDailyPlan] = {p.plan_date: p for p in plans}

    tz = ZoneInfo(timezone_name) if ZoneInfo else datetime.timezone.utc
    now_local = datetime.datetime.now(datetime.timezone.utc).astimezone(tz)
    today_local = now_local.date()

    rows: list[DailyReportRow] = []
    d = date_from
    while d <= date_to:
        plan = plan_by_date.get(d)
        if plan is None:
            plan = AnprDailyPlan(godown_id=godown_id, plan_date=d, timezone_name=timezone_name)
            items: list[AnprDailyPlanItem] = []
            expected_count = None
            cutoff = datetime.time(18, 0)
        else:
            items = list(plan.items or [])
            expected_count = plan.expected_count
            cutoff = plan.cutoff_time_local or datetime.time(18, 0)

        start_utc, end_utc = _local_day_range_to_utc(plan.timezone_name or timezone_name, d)
        _, arrived_set = _verified_arrivals_for_range(
            db,
            godown_id=godown_id,
            start_utc=start_utc,
            end_utc=end_utc,
        )

        counts = defaultdict(int)
        for it in items:
            manual = _coerce_status(it.status) if it.status else None
            if manual == "CANCELLED":
                counts["cancelled"] += 1
                continue
            if it.plate_norm in arrived_set:
                counts["arrived"] += 1
                continue
            if d < today_local:
                counts["no_show"] += 1
                continue
            if d > today_local:
                counts["planned"] += 1
                continue
            # today
            if now_local.time() >= cutoff:
                counts["no_show"] += 1
            elif it.expected_by_local and now_local.time() >= it.expected_by_local:
                counts["delayed"] += 1
            else:
                counts["planned"] += 1

        rows.append(
            DailyReportRow(
                date_local=d,
                expected_count=expected_count,
                planned_items=len(items),
                arrived=int(counts["arrived"]),
                delayed=int(counts["delayed"]),
                no_show=int(counts["no_show"]),
                cancelled=int(counts["cancelled"]),
            )
        )
        d = d + datetime.timedelta(days=1)

    return DailyReportOut(godown_id=godown_id, timezone_name=timezone_name, rows=rows)
