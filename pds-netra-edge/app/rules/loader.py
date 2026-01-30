"""
Rule loading for PDS Netra.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import List

from ..config import Settings


def _norm_zone_id(z: str | None) -> str:
    zz = (z or "").strip()
    if not zz or zz.lower() in {"all", "*", "__global__", "global"}:
        return "__GLOBAL__"
    return zz


@dataclass
class BaseRule:
    id: str
    type: str
    camera_id: str
    zone_id: str


@dataclass
class UnauthPersonAfterHoursRule(BaseRule):
    start_time: str
    end_time: str


@dataclass
class NoPersonDuringRule(BaseRule):
    start: str
    end: str


@dataclass
class LoiteringRule(BaseRule):
    threshold_seconds: int = 60


@dataclass
class AnimalForbiddenRule(BaseRule):
    pass


@dataclass
class BagMovementAfterHoursRule(BaseRule):
    start_time: str
    end_time: str


@dataclass
class BagMovementMonitorRule(BaseRule):
    threshold_distance: int = 50


@dataclass
class BagMonitorRule(BaseRule):
    cooldown_seconds: int = 60


@dataclass
class BagOddHoursRule(BaseRule):
    start_local: str
    end_local: str
    cooldown_seconds: int = 60


@dataclass
class BagUnplannedRule(BaseRule):
    require_active_dispatch_plan: bool = True
    cooldown_seconds: int = 60


@dataclass
class BagTallyMismatchRule(BaseRule):
    allowed_overage_percent: float = 0.0
    cooldown_seconds: int = 120


@dataclass
class AnprMonitorRule(BaseRule):
    pass


@dataclass
class AnprWhitelistRule(BaseRule):
    allowed_plates: List[str] = field(default_factory=list)


@dataclass
class AnprBlacklistRule(BaseRule):
    blocked_plates: List[str] = field(default_factory=list)


def load_rules(settings: Settings) -> List[BaseRule]:
    typed_rules: List[BaseRule] = []
    for rule_cfg in settings.rules:
        rule_type = rule_cfg.type
        zone_id = _norm_zone_id(getattr(rule_cfg, "zone_id", None))

        if rule_type == "UNAUTH_PERSON_AFTER_HOURS":
            typed_rules.append(
                UnauthPersonAfterHoursRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=zone_id,
                    start_time=getattr(rule_cfg, "start_time"),
                    end_time=getattr(rule_cfg, "end_time"),
                )
            )
        elif rule_type == "NO_PERSON_DURING":
            typed_rules.append(
                NoPersonDuringRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=zone_id,
                    start=getattr(rule_cfg, "start"),
                    end=getattr(rule_cfg, "end"),
                )
            )
        elif rule_type == "LOITERING":
            threshold = getattr(rule_cfg, "threshold_seconds", None)
            try:
                threshold_int = int(threshold) if threshold is not None else 60
            except ValueError:
                threshold_int = 60
            typed_rules.append(
                LoiteringRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=zone_id,
                    threshold_seconds=threshold_int,
                )
            )
        elif rule_type == "ANIMAL_FORBIDDEN":
            typed_rules.append(AnimalForbiddenRule(id=rule_cfg.id, type=rule_cfg.type, camera_id=rule_cfg.camera_id, zone_id=zone_id))
        elif rule_type == "BAG_MOVEMENT_AFTER_HOURS":
            typed_rules.append(
                BagMovementAfterHoursRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=zone_id,
                    start_time=getattr(rule_cfg, "start_time"),
                    end_time=getattr(rule_cfg, "end_time"),
                )
            )
        elif rule_type == "BAG_MOVEMENT_MONITOR":
            threshold = getattr(rule_cfg, "threshold_distance", None)
            try:
                threshold_px = int(threshold) if threshold is not None else 50
            except ValueError:
                threshold_px = 50
            typed_rules.append(
                BagMovementMonitorRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=zone_id,
                    threshold_distance=threshold_px,
                )
            )
        elif rule_type == "BAG_MONITOR":
            cooldown = getattr(rule_cfg, "cooldown_seconds", None)
            try:
                cooldown_sec = int(cooldown) if cooldown is not None else 60
            except Exception:
                cooldown_sec = 60
            typed_rules.append(BagMonitorRule(id=rule_cfg.id, type=rule_cfg.type, camera_id=rule_cfg.camera_id, zone_id=zone_id, cooldown_seconds=cooldown_sec))
        elif rule_type == "BAG_ODD_HOURS":
            cooldown = getattr(rule_cfg, "cooldown_seconds", None)
            try:
                cooldown_sec = int(cooldown) if cooldown is not None else 60
            except Exception:
                cooldown_sec = 60
            typed_rules.append(
                BagOddHoursRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=zone_id,
                    start_local=getattr(rule_cfg, "start_local"),
                    end_local=getattr(rule_cfg, "end_local"),
                    cooldown_seconds=cooldown_sec,
                )
            )
        elif rule_type == "BAG_UNPLANNED":
            cooldown = getattr(rule_cfg, "cooldown_seconds", None)
            try:
                cooldown_sec = int(cooldown) if cooldown is not None else 60
            except Exception:
                cooldown_sec = 60
            require_plan = getattr(rule_cfg, "require_active_dispatch_plan", True)
            typed_rules.append(
                BagUnplannedRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=zone_id,
                    require_active_dispatch_plan=bool(require_plan),
                    cooldown_seconds=cooldown_sec,
                )
            )
        elif rule_type == "BAG_TALLY_MISMATCH":
            cooldown = getattr(rule_cfg, "cooldown_seconds", None)
            try:
                cooldown_sec = int(cooldown) if cooldown is not None else 120
            except Exception:
                cooldown_sec = 120
            allowed = getattr(rule_cfg, "allowed_overage_percent", None)
            try:
                allowed_pct = float(allowed) if allowed is not None else 0.0
            except Exception:
                allowed_pct = 0.0
            typed_rules.append(
                BagTallyMismatchRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=zone_id,
                    allowed_overage_percent=allowed_pct,
                    cooldown_seconds=cooldown_sec,
                )
            )
        elif rule_type == "ANPR_MONITOR":
            typed_rules.append(AnprMonitorRule(id=rule_cfg.id, type=rule_cfg.type, camera_id=rule_cfg.camera_id, zone_id=zone_id))
        elif rule_type == "ANPR_WHITELIST_ONLY":
            allowed = getattr(rule_cfg, "allowed_plates", []) or []
            typed_rules.append(
                AnprWhitelistRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=zone_id,
                    allowed_plates=list(allowed),
                )
            )
        elif rule_type == "ANPR_BLACKLIST_ALERT":
            blocked = getattr(rule_cfg, "blocked_plates", []) or []
            typed_rules.append(
                AnprBlacklistRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=zone_id,
                    blocked_plates=list(blocked),
                )
            )
        else:
            continue

    return typed_rules

def get_rules_for_camera_zone(
    rules: list[BaseRule],
    camera_id: str,
    zone_id: str | None,
) -> list[BaseRule]:
    """
    Return rules that match camera_id and zone_id.
    - zone_id supports None / 'all' -> global rules.
    - Always includes GLOBAL rules (zone='__GLOBAL__') for that camera.
    """
    zid = _norm_zone_id(zone_id)
    out: list[BaseRule] = []
    for r in rules or []:
        if getattr(r, "camera_id", None) != camera_id:
            continue
        rz = _norm_zone_id(getattr(r, "zone_id", None))
        if rz == "__GLOBAL__":
            out.append(r)
            continue
        if zid != "__GLOBAL__" and rz == zid:
            out.append(r)
    return out


def get_rules_for_camera(
    rules: list[BaseRule],
    camera_id: str,
) -> list[BaseRule]:
    """Return all rules matching this camera (any zone)."""
    return [r for r in (rules or []) if getattr(r, "camera_id", None) == camera_id]

def get_anpr_rules_for_camera_zone(
    rules: list[BaseRule],
    camera_id: str,
    zone_id: str | None,
) -> list[BaseRule]:
    """
    Return ONLY ANPR-related rules for a camera+zone.
    Always includes GLOBAL rules for that camera.
    """
    cam_zone_rules = get_rules_for_camera_zone(rules, camera_id=camera_id, zone_id=zone_id)
    return [
        r
        for r in cam_zone_rules
        if isinstance(r, (AnprMonitorRule, AnprWhitelistRule, AnprBlacklistRule))
        or getattr(r, "type", "") in {"ANPR_MONITOR", "ANPR_WHITELIST_ONLY", "ANPR_BLACKLIST_ALERT"}
    ]
