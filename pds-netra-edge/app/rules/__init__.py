"""
Rules package for PDS Netra.

This package contains data models and helper functions for loading and
evaluating PDS Netra rules. Rules are defined in the YAML
configuration and control when to raise unauthorized person and
loitering events.
"""

from .loader import (
    BaseRule,
    UnauthPersonAfterHoursRule,
    NoPersonDuringRule,
    LoiteringRule,
    AnimalForbiddenRule,
    BagMovementAfterHoursRule,
    BagMovementMonitorRule,
    AnprMonitorRule,
    AnprWhitelistRule,
    AnprBlacklistRule,
    load_rules,
    get_rules_for_camera_zone,
    get_anpr_rules_for_camera_zone,
)
from .evaluator import RulesEvaluator

__all__ = [
    'BaseRule',
    'UnauthPersonAfterHoursRule',
    'NoPersonDuringRule',
    'LoiteringRule',
    'AnimalForbiddenRule',
    'BagMovementAfterHoursRule',
    'BagMovementMonitorRule',
    'AnprMonitorRule',
    'AnprWhitelistRule',
    'AnprBlacklistRule',
    'load_rules',
    'get_rules_for_camera_zone',
    'get_anpr_rules_for_camera_zone',
    'RulesEvaluator',
]