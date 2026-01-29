"""
HQ alert report generation and scheduling helpers.
"""

from __future__ import annotations

import datetime
import os
from typing import Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from ..models.event import Alert, Event
from ..models.alert_report import AlertReport
from .notification_outbox import enqueue_report_notifications


IST = ZoneInfo("Asia/Kolkata")


def _to_ist(ts: datetime.datetime) -> datetime.datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.timezone.utc)
    return ts.astimezone(IST)


def _period_range(period: str, now_utc: Optional[datetime.datetime] = None) -> Tuple[datetime.datetime, datetime.datetime]:
    now_utc = now_utc or datetime.datetime.now(datetime.timezone.utc)
    if period == "1h":
        return now_utc - datetime.timedelta(hours=1), now_utc
    # default: previous day in IST
    now_ist = now_utc.astimezone(IST)
    prev_date = (now_ist.date() - datetime.timedelta(days=1))
    start_ist = datetime.datetime.combine(prev_date, datetime.time(0, 0, 0), tzinfo=IST)
    end_ist = start_ist + datetime.timedelta(days=1)
    return start_ist.astimezone(datetime.timezone.utc), end_ist.astimezone(datetime.timezone.utc)


def _dispatch_delay_counts(alerts: list[Alert]) -> dict:
    counts: dict[str, int] = {}
    for alert in alerts:
        extra = alert.extra if isinstance(alert.extra, dict) else {}
        threshold = extra.get("threshold_hours")
        if threshold is None:
            continue
        key = str(threshold)
        counts[key] = counts.get(key, 0) + 1
    return counts


def generate_hq_report(
    db: Session,
    *,
    period: str = "24h",
    now_utc: Optional[datetime.datetime] = None,
    force: bool = False,
) -> AlertReport:
    period = period if period in {"24h", "1h"} else "24h"
    period_start, period_end = _period_range(period, now_utc)
    existing = (
        db.query(AlertReport)
        .filter(
            AlertReport.scope == "HQ",
            AlertReport.period_start == period_start,
            AlertReport.period_end == period_end,
        )
        .first()
    )
    if existing and not force:
        return existing
    alerts_q = db.query(Alert).filter(
        Alert.start_time >= period_start,
        Alert.start_time < period_end,
    )
    alerts = alerts_q.all()

    alert_counts = dict(
        db.query(Alert.alert_type, func.count(Alert.id))
        .filter(Alert.start_time >= period_start, Alert.start_time < period_end)
        .group_by(Alert.alert_type)
        .all()
    )

    godown_counts = (
        db.query(Alert.godown_id, func.count(Alert.id))
        .filter(Alert.start_time >= period_start, Alert.start_time < period_end)
        .group_by(Alert.godown_id)
        .order_by(func.count(Alert.id).desc())
        .limit(5)
        .all()
    )
    top_godowns = [{"godown_id": gid, "count": cnt} for gid, cnt in godown_counts]

    offline_count = (
        db.query(func.count(Event.id))
        .filter(
            Event.event_type == "CAMERA_OFFLINE",
            Event.timestamp_utc >= period_start,
            Event.timestamp_utc < period_end,
        )
        .scalar()
        or 0
    )
    blackout_count = 0
    blackout_events = db.query(Event).filter(
        Event.timestamp_utc >= period_start,
        Event.timestamp_utc < period_end,
    ).all()
    for ev in blackout_events:
        meta = ev.meta or {}
        reason = (meta.get("reason") or "").upper() if isinstance(meta, dict) else ""
        if reason in {"SUDDEN_BLACKOUT", "BLACK_FRAME"}:
            blackout_count += 1

    open_critical = (
        db.query(func.count(Alert.id))
        .filter(Alert.status == "OPEN", Alert.severity_final == "critical")
        .scalar()
        or 0
    )

    dispatch_alerts = [a for a in alerts if a.alert_type == "DISPATCH_MOVEMENT_DELAY"]
    dispatch_counts = _dispatch_delay_counts(dispatch_alerts)

    summary = {
        "period": period,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "total_alerts": len(alerts),
        "alerts_by_type": alert_counts,
        "top_godowns": top_godowns,
        "camera_health": {
            "offline_events": offline_count,
            "blackout_events": blackout_count,
        },
        "open_critical_alerts": open_critical,
        "dispatch_delay_counts": dispatch_counts,
    }

    period_label = "Daily" if period == "24h" else "Hourly"
    start_ist = _to_ist(period_start)
    end_ist = _to_ist(period_end - datetime.timedelta(seconds=1))
    period_text = f"{start_ist.strftime('%d %b %Y %H:%M')}–{end_ist.strftime('%H:%M')} IST"
    top_godown_text = ", ".join([f"{g['godown_id']}({g['count']})" for g in top_godowns]) or "N/A"
    dispatch_text = ", ".join([f"{k}h:{v}" for k, v in dispatch_counts.items()]) or "none"

    message_text = (
        f"HQ {period_label} Alert Report\n"
        f"Period: {period_text}\n"
        f"Total alerts: {len(alerts)} | Critical open: {open_critical}\n"
        f"Top godowns: {top_godown_text}\n"
        f"Health: offline {offline_count}, blackout {blackout_count}\n"
        f"Dispatch delays: {dispatch_text}"
    )

    base_url = (os.getenv("DASHBOARD_BASE_URL") or "").rstrip("/")
    link_html = ""
    if base_url:
        link_html = (
            f"<p><strong>Dashboard:</strong> "
            f"<a href=\"{base_url}/dashboard/alerts?date_from={period_start.isoformat()}&date_to={period_end.isoformat()}\">"
            f"Open alerts view</a></p>"
        )
    email_html = (
        f"<h3>HQ {period_label} Alert Report</h3>"
        f"<p><strong>Period:</strong> {period_text}</p>"
        f"<p><strong>Total alerts:</strong> {len(alerts)}</p>"
        f"<p><strong>Critical open alerts:</strong> {open_critical}</p>"
        f"<p><strong>Top godowns:</strong> {top_godown_text}</p>"
        f"<p><strong>Camera health:</strong> offline {offline_count}, blackout {blackout_count}</p>"
        f"<p><strong>Dispatch delays:</strong> {dispatch_text}</p>"
        f"{link_html}"
        f"<h4>Alerts by type</h4>"
        f"<ul>"
        + "".join([f"<li>{k}: {v}</li>" for k, v in alert_counts.items()])
        + "</ul>"
    )

    report = AlertReport(
        scope="HQ",
        period_start=period_start,
        period_end=period_end,
        generated_at=datetime.datetime.now(datetime.timezone.utc),
        summary_json=summary,
        message_text=message_text,
        email_html=email_html,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    enqueue_report_notifications(
        db,
        report_id=report.id,
        message_text=report.message_text,
        email_html=report.email_html,
        subject=f"PDS Netra HQ {period_label} Alert Report",
    )
    return report
