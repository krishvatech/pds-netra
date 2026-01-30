from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import csv
import os
from collections import defaultdict
from typing import List, Dict, Any

router = APIRouter(prefix="/api/v1/anpr", tags=["ANPR"])

# Config
ANPR_CSV_BASE = os.getenv("ANPR_CSV_DIR", "data/anpr_csv")
DEFAULT_GAP_SECONDS = 300  # 5 minutes


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


@router.get("/sessions")
def get_anpr_sessions(
    godown_id: str = Query(...),
    timezone_name: str = Query("Asia/Kolkata"),
    gap_seconds: int = Query(DEFAULT_GAP_SECONDS),
):
    tz = ZoneInfo(timezone_name)

    csv_dir = os.path.join(ANPR_CSV_BASE, godown_id)
    if not os.path.exists(csv_dir):
        raise HTTPException(status_code=404, detail="CSV directory not found")

    csv_files = [f for f in os.listdir(csv_dir) if f.endswith(".csv")]
    if not csv_files:
        raise HTTPException(status_code=404, detail="No ANPR CSV files found")

    rows: List[Dict[str, Any]] = []

    for fname in csv_files:
        with open(os.path.join(csv_dir, fname), newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(r)

    if not rows:
        return {"sessions": []}

    # sort by time
    rows.sort(key=lambda r: r["timestamp_utc"])

    # group by plate + camera
    grouped = defaultdict(list)
    for r in rows:
        key = (r["plate_text"], r["camera_id"])
        grouped[key].append(r)

    sessions = []

    for (plate, camera), events in grouped.items():
        start = _parse_ts(events[0]["timestamp_utc"])
        last_seen = start

        max_conf = 0.0
        final_status = events[0].get("match_status", "UNKNOWN")

        for ev in events:
            ts = _parse_ts(ev["timestamp_utc"])
            conf = float(ev.get("combined_conf", 0.0))
            max_conf = max(max_conf, conf)
            final_status = ev.get("match_status", final_status)

            if (ts - last_seen).total_seconds() > gap_seconds:
                # close previous session
                sessions.append({
                    "plate_text": plate,
                    "plate_status": final_status,
                    "entry_time_local": start.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S"),
                    "exit_time_local": last_seen.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S"),
                    "duration_seconds": int((last_seen - start).total_seconds()),
                    "confidence": round(max_conf, 3),
                    "camera_id": camera,
                    "session_status": "CLOSED",
                })
                # start new session
                start = ts
                max_conf = conf

            last_seen = ts

        # final session (ACTIVE or CLOSED)
        now_utc = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
        active = (now_utc - last_seen).total_seconds() <= gap_seconds

        sessions.append({
            "plate_text": plate,
            "plate_status": final_status,
            "entry_time_local": start.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S"),
            "exit_time_local": None if active else last_seen.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": None if active else int((last_seen - start).total_seconds()),
            "confidence": round(max_conf, 3),
            "camera_id": camera,
            "session_status": "ACTIVE" if active else "CLOSED",
        })

    return {"sessions": sessions}
