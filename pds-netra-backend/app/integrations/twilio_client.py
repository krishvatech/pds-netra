"""Helpers to build Twilio REST clients for messaging and voice."""

from __future__ import annotations

import os

from twilio.rest import Client

from ..core.config import settings


def _resolve_config(attr: str, legacy_env: str) -> str | None:
    value = getattr(settings, attr, None)
    if value:
        return value
    return os.getenv(legacy_env)


def _ensure(value: str | None, name: str) -> str:
    if not value:
        raise RuntimeError(f"Twilio config missing: {name}")
    return value


def get_twilio_messaging_client() -> Client:
    account_sid = _resolve_config("TWILIO_MSG_ACCOUNT_SID", "TWILIO_ACCOUNT_SID")
    auth_token = _resolve_config("TWILIO_MSG_AUTH_TOKEN", "TWILIO_AUTH_TOKEN")
    account_sid = _ensure(account_sid, "TWILIO_MSG_ACCOUNT_SID or TWILIO_ACCOUNT_SID")
    auth_token = _ensure(auth_token, "TWILIO_MSG_AUTH_TOKEN or TWILIO_AUTH_TOKEN")
    return Client(account_sid, auth_token)


def get_twilio_voice_client() -> Client:
    account_sid = _resolve_config("TWILIO_VOICE_ACCOUNT_SID", "TWILIO_ACCOUNT_SID")
    auth_token = _resolve_config("TWILIO_VOICE_AUTH_TOKEN", "TWILIO_AUTH_TOKEN")
    account_sid = _ensure(account_sid, "TWILIO_VOICE_ACCOUNT_SID or TWILIO_ACCOUNT_SID")
    auth_token = _ensure(auth_token, "TWILIO_VOICE_AUTH_TOKEN or TWILIO_AUTH_TOKEN")
    return Client(account_sid, auth_token)
