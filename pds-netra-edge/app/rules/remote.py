"""
Fetch rule configurations from the backend API.
"""

from __future__ import annotations

import json
import os
import logging
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable, List, Optional

from ..config import RuleConfig


RULE_FIELDS = {
    "id",
    "type",
    "camera_id",
    "zone_id",
    "start_time",
    "end_time",
    "start",
    "end",
    "threshold_seconds",
    "start_local",
    "end_local",
    "cooldown_seconds",
    "require_active_dispatch_plan",
    "allowed_overage_percent",
    "threshold_distance",
    "allowed_plates",
    "blocked_plates",
}


def _normalize_list(value) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return None


def _coerce_rule(item: dict) -> Optional[RuleConfig]:
    if not isinstance(item, dict):
        return None
    data = {k: item.get(k) for k in RULE_FIELDS if k in item}
    rule_id = item.get("id")
    if rule_id is None:
        return None
    data["id"] = str(rule_id)
    if not data.get("type") or not data.get("camera_id") or not data.get("zone_id"):
        return None
    if "allowed_plates" in data:
        data["allowed_plates"] = _normalize_list(data.get("allowed_plates"))
    if "blocked_plates" in data:
        data["blocked_plates"] = _normalize_list(data.get("blocked_plates"))
    try:
        return RuleConfig(**data)
    except Exception:
        return None


def fetch_rule_configs(
    backend_url: str,
    godown_id: str,
    timeout_sec: float = 3.0,
) -> Optional[List[RuleConfig]]:
    logger = logging.getLogger("rules.remote")
    base = backend_url.rstrip("/")
    query = urllib.parse.urlencode({"godown_id": godown_id})
    url = f"{base}/api/v1/rules/active?{query}"
    token = (os.getenv("EDGE_BACKEND_TOKEN") or "").strip()
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.warning("Failed to fetch rules from %s: %s", url, exc)
        cached = load_cached_rules()
        if cached:
            logger.info("Loaded %s rules from cache", len(cached))
        return cached
    items = None
    if isinstance(payload, dict):
        items = payload.get("items")
    if items is None:
        if isinstance(payload, list):
            items = payload
        else:
            return None
    rules: List[RuleConfig] = []
    for raw in items:
        rule = _coerce_rule(raw)
        if rule is not None:
            rules.append(rule)
    if rules:
        save_cached_rules(rules)
    return rules


def _cache_path() -> Path:
    cache_path = os.getenv("EDGE_RULES_CACHE_PATH", "data/rules_cache.json")
    path = Path(cache_path).expanduser()
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def save_cached_rules(rules: List[RuleConfig]) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"items": [r.__dict__ for r in rules]}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_cached_rules() -> Optional[List[RuleConfig]]:
    path = _cache_path()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return None
    rules: List[RuleConfig] = []
    for raw in items:
        rule = _coerce_rule(raw)
        if rule is not None:
            rules.append(rule)
    return rules or None
