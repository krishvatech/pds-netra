"""
Camera pipeline routing utilities.

This module resolves per-camera roles and module flags into a concrete
set of enabled detection features. It keeps backwards compatibility for
older configs that do not specify roles/modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..config import CameraConfig, CameraModules, Settings


ROLE_GATE_ANPR = "GATE_ANPR"
ROLE_SECURITY = "SECURITY"
ROLE_HEALTH_ONLY = "HEALTH_ONLY"


@dataclass(frozen=True)
class ResolvedModules:
    anpr_enabled: bool
    gate_entry_exit_enabled: bool
    person_after_hours_enabled: bool
    animal_detection_enabled: bool
    fire_detection_enabled: bool
    health_monitoring_enabled: bool


@dataclass(frozen=True)
class CameraPipeline:
    camera: CameraConfig
    role: str
    modules: ResolvedModules


class SecurityPipeline(CameraPipeline):
    pass


class AnprGatePipeline(CameraPipeline):
    pass


class HealthOnlyPipeline(CameraPipeline):
    pass


def _normalize_role(role: Optional[str]) -> str:
    if not role:
        return ROLE_SECURITY
    role = str(role).strip().upper()
    if role in {ROLE_GATE_ANPR, ROLE_SECURITY, ROLE_HEALTH_ONLY}:
        return role
    return ROLE_SECURITY


def _resolve_base_modules(camera: CameraConfig, settings: Settings) -> dict[str, bool]:
    role = _normalize_role(camera.role)
    # Keep backward compatibility for old cameras, but if a specialized role
    # is present from backend (GATE_ANPR / HEALTH_ONLY), honor it even when
    # role_explicit is false.
    legacy_defaults = (
        not getattr(camera, "role_explicit", False)
        and role not in {ROLE_GATE_ANPR, ROLE_HEALTH_ONLY}
    )

    if legacy_defaults:
        return {
            "anpr_enabled": bool(settings.anpr and settings.anpr.enabled),
            "gate_entry_exit_enabled": bool(settings.anpr and settings.anpr.enabled),
            "person_after_hours_enabled": bool(settings.after_hours_presence and settings.after_hours_presence.enabled),
            "animal_detection_enabled": True,
            "fire_detection_enabled": bool(settings.fire_detection and settings.fire_detection.enabled),
            "health_monitoring_enabled": True,
        }

    if role == ROLE_GATE_ANPR:
        return {
            "anpr_enabled": True,
            "gate_entry_exit_enabled": True,
            "person_after_hours_enabled": False,
            "animal_detection_enabled": False,
            "fire_detection_enabled": False,
            "health_monitoring_enabled": True,
        }
    if role == ROLE_HEALTH_ONLY:
        return {
            "anpr_enabled": False,
            "gate_entry_exit_enabled": False,
            "person_after_hours_enabled": False,
            "animal_detection_enabled": False,
            "fire_detection_enabled": False,
            "health_monitoring_enabled": True,
        }

    return {
        "anpr_enabled": False,
        "gate_entry_exit_enabled": False,
        "person_after_hours_enabled": bool(settings.after_hours_presence and settings.after_hours_presence.enabled),
        "animal_detection_enabled": True,
        "fire_detection_enabled": bool(settings.fire_detection and settings.fire_detection.enabled),
        "health_monitoring_enabled": True,
    }


def _apply_module_overrides(base: dict[str, bool], modules: Optional[CameraModules]) -> dict[str, bool]:
    if not modules:
        return base
    overrides = {
        "anpr_enabled": modules.anpr_enabled,
        "gate_entry_exit_enabled": modules.gate_entry_exit_enabled,
        "person_after_hours_enabled": modules.person_after_hours_enabled,
        "animal_detection_enabled": modules.animal_detection_enabled,
        "fire_detection_enabled": modules.fire_detection_enabled,
        "health_monitoring_enabled": modules.health_monitoring_enabled,
    }
    for key, value in overrides.items():
        if value is not None:
            base[key] = bool(value)
    return base


def resolve_camera_modules(camera: CameraConfig, settings: Settings) -> ResolvedModules:
    base = _resolve_base_modules(camera, settings)
    base = _apply_module_overrides(base, camera.modules)

    # Global safeguards: disable modules when global config is missing or disabled.
    if not settings.anpr or not settings.anpr.enabled:
        base["anpr_enabled"] = False
        base["gate_entry_exit_enabled"] = False
    if not settings.after_hours_presence or not settings.after_hours_presence.enabled:
        base["person_after_hours_enabled"] = False
    if not settings.fire_detection or not settings.fire_detection.enabled:
        base["fire_detection_enabled"] = False

    return ResolvedModules(
        anpr_enabled=base["anpr_enabled"],
        gate_entry_exit_enabled=base["gate_entry_exit_enabled"],
        person_after_hours_enabled=base["person_after_hours_enabled"],
        animal_detection_enabled=base["animal_detection_enabled"],
        fire_detection_enabled=base["fire_detection_enabled"],
        health_monitoring_enabled=base["health_monitoring_enabled"],
    )


def select_pipeline(camera: CameraConfig, settings: Settings) -> CameraPipeline:
    role = _normalize_role(camera.role)
    modules = resolve_camera_modules(camera, settings)
    if role == ROLE_GATE_ANPR:
        return AnprGatePipeline(camera=camera, role=role, modules=modules)
    if role == ROLE_HEALTH_ONLY:
        return HealthOnlyPipeline(camera=camera, role=role, modules=modules)
    return SecurityPipeline(camera=camera, role=role, modules=modules)
