"""
Reporting endpoints for PDS Netra backend.

These endpoints produce aggregated summaries of events and alerts. For
demonstration purposes, only a simple count by alert_type is provided.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from fastapi import APIRouter, Depends, Query, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.auth import require_roles
from ...models.event import Alert, Event
from ...models.dispatch_issue import DispatchIssue
from ...models.alert_report import AlertReport
from ...models.notification_outbox import NotificationOutbox
from ...schemas.alert_report import AlertReportListItem, AlertReportOut
from ...schemas.notifications import NotificationDeliveryOut
from ...services.alert_reports import generate_hq_report
from ...core.pagination import clamp_page_size, clamp_limit, set_pagination_headers


router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/alerts/summary")
def alert_summary(
    godown_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> Dict[str, int]:
    """Return a simple count of open alerts by alert_type."""
    query = db.query(Alert)
    if godown_id:
        query = query.filter(Alert.godown_id == godown_id)
    query = query.filter(Alert.status == "OPEN")
    counts: Dict[str, int] = {}
    for alert in query:
        counts[alert.alert_type] = counts.get(alert.alert_type, 0) + 1
    return counts


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _bucket_ts(ts: datetime, bucket: str) -> datetime:
    ts = _ensure_utc(ts)
    if bucket == "day":
        return ts.replace(hour=0, minute=0, second=0, microsecond=0)
    return ts.replace(minute=0, second=0, microsecond=0)


def _movement_query(
    db: Session,
    godown_id: Optional[str],
    camera_id: Optional[str],
    zone_id: Optional[str],
    date_from: Optional[datetime],
    date_to: Optional[datetime],
):
    query = db.query(Event).filter(Event.event_type == "BAG_MOVEMENT")
    if godown_id:
        query = query.filter(Event.godown_id == godown_id)
    if camera_id:
        query = query.filter(Event.camera_id == camera_id)
    if date_from:
        query = query.filter(Event.timestamp_utc >= _ensure_utc(date_from))
    if date_to:
        query = query.filter(Event.timestamp_utc <= _ensure_utc(date_to))
    if zone_id:
        # Fallback to python-level filter for JSON to avoid dialect issues
        events = query.order_by(Event.timestamp_utc.asc()).all()
        return [e for e in events if (e.meta or {}).get("zone_id") == zone_id]
    return query.order_by(Event.timestamp_utc.asc()).all()


@router.get("/movement/summary")
def movement_summary(
    godown_id: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    """Return summary counts for bag movement activity."""
    now = datetime.now(timezone.utc)
    if not date_from and not date_to:
        date_from = now - timedelta(days=7)
        date_to = now
    events = _movement_query(db, godown_id, camera_id, zone_id, date_from, date_to)
    counts_by_type: Dict[str, int] = {}
    unique_plans: set[str] = set()
    for ev in events:
        meta = ev.meta or {}
        movement_type = str(meta.get("movement_type") or "UNKNOWN")
        counts_by_type[movement_type] = counts_by_type.get(movement_type, 0) + 1
        extra = meta.get("extra") or {}
        plan_id = extra.get("plan_id") if isinstance(extra, dict) else None
        if plan_id:
            unique_plans.add(str(plan_id))
    return {
        "range": {
            "from": _ensure_utc(date_from).isoformat().replace("+00:00", "Z") if date_from else None,
            "to": _ensure_utc(date_to).isoformat().replace("+00:00", "Z") if date_to else None,
        },
        "total_events": len(events),
        "unique_plans": len(unique_plans),
        "counts_by_type": counts_by_type,
    }


@router.get("/movement/timeline")
def movement_timeline(
    bucket: str = Query("hour"),
    godown_id: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    """Return a time-bucketed series of bag movement events."""
    bucket = "day" if bucket == "day" else "hour"
    now = datetime.now(timezone.utc)
    if not date_from and not date_to:
        date_from = now - timedelta(days=7)
        date_to = now
    events = _movement_query(db, godown_id, camera_id, zone_id, date_from, date_to)
    counts: Dict[Tuple[datetime, str], int] = {}
    for ev in events:
        meta = ev.meta or {}
        movement_type = str(meta.get("movement_type") or "UNKNOWN")
        ts = _bucket_ts(ev.timestamp_utc, bucket)
        key = (ts, movement_type)
        counts[key] = counts.get(key, 0) + 1
    items = [
        {
            "t": ts.isoformat().replace("+00:00", "Z"),
            "movement_type": movement_type,
            "count": count,
        }
        for (ts, movement_type), count in sorted(counts.items(), key=lambda x: x[0][0])
    ]
    return {
        "bucket": bucket,
        "items": items,
        "range": {
            "from": _ensure_utc(date_from).isoformat().replace("+00:00", "Z") if date_from else None,
            "to": _ensure_utc(date_to).isoformat().replace("+00:00", "Z") if date_to else None,
        },
    }


def _find_first_movement(db: Session, issue: DispatchIssue) -> Optional[Event]:
    query = db.query(Event).filter(
        Event.godown_id == issue.godown_id,
        Event.event_type == "BAG_MOVEMENT",
        Event.timestamp_utc >= issue.issue_time_utc,
    )
    if issue.camera_id:
        query = query.filter(Event.camera_id == issue.camera_id)
    query = query.order_by(Event.timestamp_utc.asc())
    if not issue.zone_id:
        return query.first()
    for event in query.yield_per(200):
        meta = event.meta or {}
        if meta.get("zone_id") == issue.zone_id:
            return event
    return None


def _count_movement_24h(db: Session, issue: DispatchIssue) -> int:
    issue_time = _ensure_utc(issue.issue_time_utc)
    deadline = issue_time + timedelta(hours=24)
    query = db.query(Event).filter(
        Event.godown_id == issue.godown_id,
        Event.event_type == "BAG_MOVEMENT",
        Event.timestamp_utc >= issue_time,
        Event.timestamp_utc <= deadline,
    )
    if issue.camera_id:
        query = query.filter(Event.camera_id == issue.camera_id)
    if not issue.zone_id:
        return query.count()
    count = 0
    for event in query.yield_per(200):
        meta = event.meta or {}
        if meta.get("zone_id") == issue.zone_id:
            count += 1
    return count


@router.get("/dispatch-trace")
def dispatch_trace(
    godown_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    db: Session = Depends(get_db),
) -> dict:
    """Return dispatch trace details including first movement and SLA."""
    page_size = clamp_page_size(page_size)
    query = db.query(DispatchIssue)
    if godown_id:
        query = query.filter(DispatchIssue.godown_id == godown_id)
    if status:
        query = query.filter(DispatchIssue.status == status)
    if date_from:
        query = query.filter(DispatchIssue.issue_time_utc >= _ensure_utc(date_from))
    if date_to:
        query = query.filter(DispatchIssue.issue_time_utc <= _ensure_utc(date_to))
    total = query.count()
    issues = (
        query.order_by(DispatchIssue.issue_time_utc.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items: list[dict] = []
    for issue in issues:
        issue_time = _ensure_utc(issue.issue_time_utc)
        deadline = issue_time + timedelta(hours=24)
        first_event = _find_first_movement(db, issue)
        first_ts = _ensure_utc(first_event.timestamp_utc) if first_event else None
        meta = first_event.meta if first_event else {}
        movement_type = meta.get("movement_type") if isinstance(meta, dict) else None
        extra = meta.get("extra") if isinstance(meta, dict) else None
        plan_id = None
        if isinstance(extra, dict):
            plan_id = extra.get("plan_id")
        sla_met = bool(first_ts and first_ts <= deadline)
        delay_minutes = None
        if first_ts:
            delay_minutes = int((first_ts - issue_time).total_seconds() // 60)
        items.append(
            {
                "issue_id": issue.id,
                "godown_id": issue.godown_id,
                "camera_id": issue.camera_id,
                "zone_id": issue.zone_id,
                "issue_time_utc": issue_time.isoformat().replace("+00:00", "Z"),
                "deadline_utc": deadline.isoformat().replace("+00:00", "Z"),
                "status": issue.status,
                "alert_id": issue.alert_id,
                "started_at_utc": issue.started_at_utc.isoformat().replace("+00:00", "Z") if issue.started_at_utc else None,
                "alerted_at_utc": issue.alerted_at_utc.isoformat().replace("+00:00", "Z") if issue.alerted_at_utc else None,
                "first_movement_utc": first_ts.isoformat().replace("+00:00", "Z") if first_ts else None,
                "first_movement_type": movement_type,
                "plan_id": plan_id,
                "movement_count_24h": _count_movement_24h(db, issue),
                "sla_met": sla_met,
                "delay_minutes": delay_minutes,
            }
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/alerts/export")
def export_alerts_csv(
    godown_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    query = db.query(Alert)
    if godown_id:
        query = query.filter(Alert.godown_id == godown_id)
    if status:
        query = query.filter(Alert.status == status)
    if date_from:
        query = query.filter(Alert.start_time >= _ensure_utc(date_from))
    if date_to:
        query = query.filter(Alert.start_time <= _ensure_utc(date_to))
    alerts = query.order_by(Alert.start_time.desc()).all()

    def _iter():
        yield "alert_id,godown_id,camera_id,alert_type,severity,status,start_time,end_time,zone_id,summary\n"
        for a in alerts:
            row = [
                a.id,
                a.godown_id,
                a.camera_id or "",
                a.alert_type,
                a.severity_final,
                a.status,
                a.start_time.isoformat() if a.start_time else "",
                a.end_time.isoformat() if a.end_time else "",
                a.zone_id or "",
                (a.summary or "").replace("\n", " ").replace(",", " "),
            ]
            yield ",".join([str(x) for x in row]) + "\n"

    return StreamingResponse(_iter(), media_type="text/csv")


@router.get("/movement/export")
def export_movement_csv(
    godown_id: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    events = _movement_query(db, godown_id, camera_id, zone_id, date_from, date_to)

    def _iter():
        yield "event_id,godown_id,camera_id,timestamp_utc,zone_id,movement_type,plan_id,expected_bag_count,observed_bag_count,severity\n"
        for ev in events:
            meta = ev.meta or {}
            extra = meta.get("extra") if isinstance(meta, dict) else {}
            if not isinstance(extra, dict):
                extra = {}
            row = [
                ev.event_id_edge,
                ev.godown_id,
                ev.camera_id,
                ev.timestamp_utc.isoformat() if ev.timestamp_utc else "",
                meta.get("zone_id") or "",
                meta.get("movement_type") or "",
                extra.get("plan_id") or "",
                extra.get("expected_bag_count") or "",
                extra.get("observed_bag_count") or "",
                ev.severity_raw,
            ]
            yield ",".join([str(x) for x in row]) + "\n"

    return StreamingResponse(_iter(), media_type="text/csv")


@router.get("/hq", response_model=list[AlertReportListItem])
def list_hq_reports(
    limit: int = Query(30),
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN")),
    response: Response,
):
    limit = clamp_limit(int(limit))
    base_query = db.query(AlertReport).filter(AlertReport.scope == "HQ")
    total = base_query.count()
    rows = base_query.order_by(AlertReport.generated_at.desc()).limit(limit).all()
    set_pagination_headers(response, total=total, page=1, page_size=limit)
    return rows


@router.get("/hq/{report_id}", response_model=AlertReportOut)
def get_hq_report(
    report_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN")),
):
    report = db.get(AlertReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/hq/{report_id}/deliveries", response_model=list[NotificationDeliveryOut])
def get_hq_report_deliveries(
    report_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN")),
    response: Response,
):
    page_size = clamp_page_size(page_size)
    report = db.get(AlertReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    base_query = (
        db.query(NotificationOutbox)
        .filter(NotificationOutbox.report_id == report.id)
    )
    total = base_query.count()
    rows = (
        base_query.order_by(NotificationOutbox.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    set_pagination_headers(response, total=total, page=page, page_size=page_size)
    return rows


@router.post("/hq/generate", response_model=AlertReportOut)
def generate_hq_report_endpoint(
    period: str = Query("24h"),
    force: bool = Query(False),
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN")),
):
    period = period if period in {"24h", "1h"} else "24h"
    report = generate_hq_report(db, period=period, force=force)
    return report
