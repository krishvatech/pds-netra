"""
Rule loading for PDS Netra.

This module defines data classes for each supported rule type and
functions to parse generic rule definitions from the Settings object
into strongly-typed rule instances. The YAML configuration uses
simple dictionaries under ``rules``. At runtime we convert those
entries into specialised classes which make downstream evaluation
clearer and type-safe.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import List, Dict, Any

from ..config import Settings


@dataclass
class BaseRule:
    """Base class for all rule types."""

    id: str
    type: str
    camera_id: str
    zone_id: str


@dataclass
class UnauthPersonAfterHoursRule(BaseRule):
    """Rule enforcing no persons after hours in a specific zone."""

    start_time: str  # HH:MM in local timezone
    end_time: str    # HH:MM in local timezone


@dataclass
class NoPersonDuringRule(BaseRule):
    """Rule enforcing no persons during a defined time window (e.g. fumigation)."""

    start: str  # HH:MM in local timezone
    end: str    # HH:MM in local timezone


@dataclass
class LoiteringRule(BaseRule):
    """Rule describing loitering threshold in seconds."""

    threshold_seconds: int = 60


@dataclass
class AnimalForbiddenRule(BaseRule):
    """Rule forbidding the presence of animals in a zone."""
    pass


@dataclass
class BagMovementAfterHoursRule(BaseRule):
    """Rule detecting bag movement in a zone during an after-hours window."""
    start_time: str
    end_time: str


@dataclass
class BagMovementMonitorRule(BaseRule):
    """Rule detecting generic bag movement events in a zone."""
    # Optional pixel distance threshold for movement; default is 50 pixels
    threshold_distance: int = 50


@dataclass
class BagMonitorRule(BaseRule):
    """Rule emitting bag movement events for any movement inside a zone."""
    cooldown_seconds: int = 60


@dataclass
class BagOddHoursRule(BaseRule):
    """Rule emitting bag movement events during odd-hours windows."""
    start_local: str
    end_local: str
    cooldown_seconds: int = 60


@dataclass
class BagUnplannedRule(BaseRule):
    """Rule emitting bag movement events when no dispatch plan is active."""
    require_active_dispatch_plan: bool = True
    cooldown_seconds: int = 60


@dataclass
class BagTallyMismatchRule(BaseRule):
    """Rule emitting bag movement events when tally exceeds expected plan count."""
    allowed_overage_percent: float = 0.0
    cooldown_seconds: int = 120


@dataclass
class AnprMonitorRule(BaseRule):
    """Rule that enables ANPR monitoring on a zone. All detected plates will
    result in events with match_status set to "UNKNOWN" by default.
    """
    pass


@dataclass
class AnprWhitelistRule(BaseRule):
    """Rule that defines a list of whitelisted number plates. Plates not in
    this list will be reported as mismatches when the rule is enforced.
    """

    allowed_plates: List[str] = field(default_factory=list)


@dataclass
class AnprBlacklistRule(BaseRule):
    """Rule that defines a list of blacklisted number plates. Plates in
    this list will trigger mismatch alerts when detected.
    """

    blocked_plates: List[str] = field(default_factory=list)


def load_rules(settings: Settings) -> List[BaseRule]:
    """
    Convert Settings.rule definitions into typed rule instances.

    Parameters
    ----------
    settings: Settings
        The loaded settings containing generic rule dictionaries.

    Returns
    -------
    List[BaseRule]
        A list of rule objects instantiated according to their ``type``.
    """
    typed_rules: List[BaseRule] = []
    for rule_cfg in settings.rules:
        rule_type = rule_cfg.type
        if rule_type == 'UNAUTH_PERSON_AFTER_HOURS':
            # Use start_time and end_time keys from the YAML
            typed_rules.append(
                UnauthPersonAfterHoursRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=rule_cfg.zone_id,
                    start_time=getattr(rule_cfg, 'start_time'),
                    end_time=getattr(rule_cfg, 'end_time'),
                )
            )
        elif rule_type == 'NO_PERSON_DURING':
            typed_rules.append(
                NoPersonDuringRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=rule_cfg.zone_id,
                    start=getattr(rule_cfg, 'start'),
                    end=getattr(rule_cfg, 'end'),
                )
            )
        elif rule_type == 'LOITERING':
            # threshold_seconds may be missing; default to 60
            threshold = getattr(rule_cfg, 'threshold_seconds', None)
            try:
                threshold_int = int(threshold) if threshold is not None else 60
            except ValueError:
                threshold_int = 60
            typed_rules.append(
                LoiteringRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=rule_cfg.zone_id,
                    threshold_seconds=threshold_int,
                )
            )
        elif rule_type == 'ANIMAL_FORBIDDEN':
            typed_rules.append(
                AnimalForbiddenRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=rule_cfg.zone_id,
                )
            )
        elif rule_type == 'BAG_MOVEMENT_AFTER_HOURS':
            typed_rules.append(
                BagMovementAfterHoursRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=rule_cfg.zone_id,
                    start_time=getattr(rule_cfg, 'start_time'),
                    end_time=getattr(rule_cfg, 'end_time'),
                )
            )
        elif rule_type == 'BAG_MOVEMENT_MONITOR':
            # threshold_distance may be specified; default to 50 if missing
            threshold = getattr(rule_cfg, 'threshold_distance', None)
            try:
                threshold_px = int(threshold) if threshold is not None else 50
            except ValueError:
                threshold_px = 50
            typed_rules.append(
                BagMovementMonitorRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=rule_cfg.zone_id,
                    threshold_distance=threshold_px,
                )
            )
        elif rule_type == 'BAG_MONITOR':
            cooldown = getattr(rule_cfg, 'cooldown_seconds', None)
            try:
                cooldown_sec = int(cooldown) if cooldown is not None else 60
            except Exception:
                cooldown_sec = 60
            typed_rules.append(
                BagMonitorRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=rule_cfg.zone_id,
                    cooldown_seconds=cooldown_sec,
                )
            )
        elif rule_type == 'BAG_ODD_HOURS':
            cooldown = getattr(rule_cfg, 'cooldown_seconds', None)
            try:
                cooldown_sec = int(cooldown) if cooldown is not None else 60
            except Exception:
                cooldown_sec = 60
            typed_rules.append(
                BagOddHoursRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=rule_cfg.zone_id,
                    start_local=getattr(rule_cfg, 'start_local'),
                    end_local=getattr(rule_cfg, 'end_local'),
                    cooldown_seconds=cooldown_sec,
                )
            )
        elif rule_type == 'BAG_UNPLANNED':
            cooldown = getattr(rule_cfg, 'cooldown_seconds', None)
            try:
                cooldown_sec = int(cooldown) if cooldown is not None else 60
            except Exception:
                cooldown_sec = 60
            require_plan = getattr(rule_cfg, 'require_active_dispatch_plan', True)
            typed_rules.append(
                BagUnplannedRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=rule_cfg.zone_id,
                    require_active_dispatch_plan=bool(require_plan),
                    cooldown_seconds=cooldown_sec,
                )
            )
        elif rule_type == 'BAG_TALLY_MISMATCH':
            cooldown = getattr(rule_cfg, 'cooldown_seconds', None)
            try:
                cooldown_sec = int(cooldown) if cooldown is not None else 120
            except Exception:
                cooldown_sec = 120
            allowed = getattr(rule_cfg, 'allowed_overage_percent', None)
            try:
                allowed_pct = float(allowed) if allowed is not None else 0.0
            except Exception:
                allowed_pct = 0.0
            typed_rules.append(
                BagTallyMismatchRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=rule_cfg.zone_id,
                    allowed_overage_percent=allowed_pct,
                    cooldown_seconds=cooldown_sec,
                )
            )
        elif rule_type == 'ANPR_MONITOR':
            # Rule to monitor all number plates without whitelist/blacklist logic
            typed_rules.append(
                AnprMonitorRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=rule_cfg.zone_id,
                )
            )
        elif rule_type == 'ANPR_WHITELIST_ONLY':
            # Rule that defines allowed plates; any other plate is considered a mismatch
            allowed = getattr(rule_cfg, 'allowed_plates', []) or []
            allowed_list = list(allowed)
            typed_rules.append(
                AnprWhitelistRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=rule_cfg.zone_id,
                    allowed_plates=allowed_list,
                )
            )
        elif rule_type == 'ANPR_BLACKLIST_ALERT':
            blocked = getattr(rule_cfg, 'blocked_plates', []) or []
            blocked_list = list(blocked)
            typed_rules.append(
                AnprBlacklistRule(
                    id=rule_cfg.id,
                    type=rule_cfg.type,
                    camera_id=rule_cfg.camera_id,
                    zone_id=rule_cfg.zone_id,
                    blocked_plates=blocked_list,
                )
            )
        else:
            # Unknown rule types are ignored; extend as needed
            continue
    return typed_rules


def get_rules_for_camera_zone(rules: List[BaseRule], camera_id: str, zone_id: str) -> List[BaseRule]:
    """
    Filter a list of rules for a specific camera and zone.

    Parameters
    ----------
    rules: List[BaseRule]
        List of rule objects.
    camera_id: str
        Identifier of the camera.
    zone_id: str
        Identifier of the zone.

    Returns
    -------
    List[BaseRule]
        The subset of rules applicable to the given camera and zone.
    """
    return [r for r in rules if r.camera_id == camera_id and r.zone_id == zone_id]


def get_anpr_rules_for_camera_zone(
    rules: List[BaseRule], camera_id: str, zone_id: str
) -> List[BaseRule]:
    """
    Filter a list of rules for ANPR-specific rules applicable to a given
    camera and zone.

    Parameters
    ----------
    rules: List[BaseRule]
        List of rule objects.
    camera_id: str
        Identifier of the camera.
    zone_id: str
        Identifier of the zone.

    Returns
    -------
    List[BaseRule]
        The subset of ANPR rules applicable to the given camera and zone.
    """
    anpr_types = (AnprMonitorRule, AnprWhitelistRule, AnprBlacklistRule)
    result: List[BaseRule] = []
    for rule in rules:
        if rule.camera_id == camera_id and rule.zone_id == zone_id and isinstance(rule, anpr_types):
            result.append(rule)
    return result
