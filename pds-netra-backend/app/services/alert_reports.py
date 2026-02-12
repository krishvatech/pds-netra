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
    godown_id: Optional[str] = None,
    scope: Optional[str] = None,
) -> AlertReport:
    period = period if period in {"24h", "1h"} else "24h"
    scope = scope or ("HQ_GODOWN" if godown_id else "HQ")
    period_start, period_end = _period_range(period, now_utc)
    existing_q = db.query(AlertReport).filter(
        AlertReport.scope == scope,
        AlertReport.period_start == period_start,
        AlertReport.period_end == period_end,
    )
    if godown_id:
        existing_q = existing_q.filter(AlertReport.godown_id == godown_id)
    else:
        existing_q = existing_q.filter(AlertReport.godown_id.is_(None))
    existing = existing_q.first()
    if existing and not force:
        return existing
    alerts_q = db.query(Alert).filter(Alert.start_time >= period_start, Alert.start_time < period_end)
    if godown_id:
        alerts_q = alerts_q.filter(Alert.godown_id == godown_id)
    alerts = alerts_q.all()

    alert_counts_q = db.query(Alert.alert_type, func.count(Alert.id)).filter(
        Alert.start_time >= period_start,
        Alert.start_time < period_end,
    )
    if godown_id:
        alert_counts_q = alert_counts_q.filter(Alert.godown_id == godown_id)
    alert_counts = dict(alert_counts_q.group_by(Alert.alert_type).all())

    if godown_id:
        top_godowns = [{"godown_id": godown_id, "count": len(alerts)}]
    else:
        godown_counts = (
            db.query(Alert.godown_id, func.count(Alert.id))
            .filter(Alert.start_time >= period_start, Alert.start_time < period_end)
            .group_by(Alert.godown_id)
            .order_by(func.count(Alert.id).desc())
            .limit(5)
            .all()
        )
        top_godowns = [{"godown_id": gid, "count": cnt} for gid, cnt in godown_counts]

    offline_q = db.query(func.count(Event.id)).filter(
        Event.event_type == "CAMERA_OFFLINE",
        Event.timestamp_utc >= period_start,
        Event.timestamp_utc < period_end,
    )
    if godown_id:
        offline_q = offline_q.filter(Event.godown_id == godown_id)
    offline_count = offline_q.scalar() or 0
    blackout_count = 0
    blackout_q = db.query(Event).filter(
        Event.timestamp_utc >= period_start,
        Event.timestamp_utc < period_end,
    )
    if godown_id:
        blackout_q = blackout_q.filter(Event.godown_id == godown_id)
    blackout_events = blackout_q.all()
    for ev in blackout_events:
        meta = ev.meta or {}
        reason = (meta.get("reason") or "").upper() if isinstance(meta, dict) else ""
        if reason in {"SUDDEN_BLACKOUT", "BLACK_FRAME"}:
            blackout_count += 1

    open_critical_q = db.query(func.count(Alert.id)).filter(
        Alert.status == "OPEN",
        Alert.severity_final == "critical",
    )
    if godown_id:
        open_critical_q = open_critical_q.filter(Alert.godown_id == godown_id)
    open_critical = open_critical_q.scalar() or 0

    dispatch_alerts = [a for a in alerts if a.alert_type == "DISPATCH_MOVEMENT_DELAY"]
    dispatch_counts = _dispatch_delay_counts(dispatch_alerts)

    summary = {
        "period": period,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "godown_id": godown_id,
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
    lines = [
        f"HQ {period_label} Alert Report",
        f"Period: {period_text}",
    ]
    if godown_id:
        lines.append(f"Godown: {godown_id}")
    lines.extend(
        [
            f"Total alerts: {len(alerts)} | Critical open: {open_critical}",
            f"Top godowns: {top_godown_text}",
            f"Health: offline {offline_count}, blackout {blackout_count}",
            f"Dispatch delays: {dispatch_text}",
        ]
    )
    message_text = "\n".join(lines)

    base_url = (os.getenv("DASHBOARD_BASE_URL") or "").rstrip("/")
    link_html = ""
    if base_url:
        link_html = (
            f"<p><strong>Dashboard:</strong> "
            f"<a href=\"{base_url}/dashboard/alerts?date_from={period_start.isoformat()}&date_to={period_end.isoformat()}\">"
            f"Open alerts view</a></p>"
        )
    godown_html = f"<p><strong>Godown:</strong> {godown_id}</p>" if godown_id else ""
    email_html = (
        f"<h3>HQ {period_label} Alert Report</h3>"
        f"<p><strong>Period:</strong> {period_text}</p>"
        f"{godown_html}"
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
        scope=scope,
        godown_id=godown_id,
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

    # Allow non-admin (GODOWN_MANAGER) recipients to receive HQ digests too.
    report_scopes = ("HQ", "GODOWN_MANAGER")
    enqueue_report_notifications(
        db,
        report_id=report.id,
        message_text=report.message_text,
        email_html=report.email_html,
        subject=f"PDS Netra HQ {period_label} Alert Report{f' - {godown_id}' if godown_id else ''}",
        scopes=report_scopes,
        godown_id=godown_id,
    )
    return report
