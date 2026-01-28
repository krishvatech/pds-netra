"""
Auto-seed baseline rules for PoC usage.
"""

from __future__ import annotations

import json
import logging
from typing import List

from sqlalchemy.orm import Session

from ..models.rule import Rule
from ..models.godown import Camera


def _parse_zones(zones_json: str | None) -> List[str]:
    if not zones_json:
        return []
    try:
        data = json.loads(zones_json)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    zones: List[str] = []
    for zone in data:
        if isinstance(zone, dict):
            zid = zone.get("id")
            if zid:
                zones.append(str(zid))
    return zones


def _rule_exists(db: Session, godown_id: str, camera_id: str, zone_id: str, rtype: str) -> bool:
    return (
        db.query(Rule)
        .filter(
            Rule.godown_id == godown_id,
            Rule.camera_id == camera_id,
            Rule.zone_id == zone_id,
            Rule.type == rtype,
        )
        .first()
        is not None
    )


def _seed_rules_for_camera(db: Session, cam: Camera) -> int:
    created = 0
    role = (cam.role or "").upper()
    cam_id = cam.id
    godown_id = cam.godown_id
    zones = _parse_zones(cam.zones_json)
    zone_targets = zones or ["all"]

    # Base security rules
    base_rules = [
        ("NO_PERSON_DURING", "all", {"start": "00:00", "end": "23:59"}),
        ("LOITERING", "all", {"threshold_seconds": 120}),
    ]
    for rtype, zone_id, params in base_rules:
        if _rule_exists(db, godown_id, cam_id, zone_id, rtype):
            continue
        db.add(
            Rule(
                godown_id=godown_id,
                camera_id=cam_id,
                zone_id=zone_id,
                type=rtype,
                enabled=True,
                params=params,
            )
        )
        created += 1

    # Animal and ANPR rules for gate/perimeter cameras
    if "GATE" in role or "PERIMETER" in role or "GATE" in cam_id.upper():
        for zone_id in zone_targets:
            for rtype, params in [
                ("ANIMAL_FORBIDDEN", {}),
                ("ANPR_MONITOR", {}),
            ]:
                if _rule_exists(db, godown_id, cam_id, zone_id, rtype):
                    continue
                db.add(
                    Rule(
                        godown_id=godown_id,
                        camera_id=cam_id,
                        zone_id=zone_id,
                        type=rtype,
                        enabled=True,
                        params=params,
                    )
                )
                created += 1

    # Bag movement rules for aisle cameras
    if "AISLE" in role or "AISLE" in cam_id.upper():
        for zone_id in zone_targets:
            for rtype, params in [
                ("BAG_MONITOR", {"cooldown_seconds": 60}),
                ("BAG_ODD_HOURS", {"start_local": "20:00", "end_local": "06:00", "cooldown_seconds": 60}),
                ("BAG_UNPLANNED", {"require_active_dispatch_plan": True, "cooldown_seconds": 60}),
                ("BAG_TALLY_MISMATCH", {"allowed_overage_percent": 10, "cooldown_seconds": 120}),
            ]:
                if _rule_exists(db, godown_id, cam_id, zone_id, rtype):
                    continue
                db.add(
                    Rule(
                        godown_id=godown_id,
                        camera_id=cam_id,
                        zone_id=zone_id,
                        type=rtype,
                        enabled=True,
                        params=params,
                    )
                )
                created += 1
    return created


def seed_rules_for_camera(db: Session, cam: Camera) -> int:
    """Seed baseline rules for a single camera."""
    created = _seed_rules_for_camera(db, cam)
    if created:
        db.commit()
        logging.getLogger("rule_seed").info("Seeded %s rules for camera %s", created, cam.id)
    return created


def seed_rules_for_godown(db: Session, godown_id: str) -> int:
    """Seed baseline rules for all cameras of a godown."""
    created = 0
    cameras = db.query(Camera).filter(Camera.godown_id == godown_id).all()
    for cam in cameras:
        created += _seed_rules_for_camera(db, cam)
    if created:
        db.commit()
        logging.getLogger("rule_seed").info("Seeded %s rules for godown %s", created, godown_id)
    return created


def seed_rules(db: Session) -> int:
    """Seed baseline rules if none exist."""
    if db.query(Rule).count() > 0:
        return 0
    created = 0
    logger = logging.getLogger("rule_seed")
    cameras = db.query(Camera).all()
    for cam in cameras:
        created += _seed_rules_for_camera(db, cam)

    if created:
        db.commit()
        logger.info("Seeded %s rules", created)
    return created