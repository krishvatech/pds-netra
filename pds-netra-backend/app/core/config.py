"""
Configuration for the PDS Netra central backend.

This module defines settings for the central backend, including
database connection and other infrastructure services. Settings
are loaded from environment variables or default values suitable
for development. Use environment variables or a `.env` file to
override as needed.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from pathlib import Path
from dotenv import load_dotenv
import logging
import os

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_PATH, override=False)



class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Database connection string. Default uses PostgreSQL on localhost.
    database_url: str = Field(
        default="postgresql+psycopg2://pdsnetra:pdsnetra@localhost:5432/pdsnetra",
        env="DATABASE_URL",
    )
    # MQTT broker URL if needed by consumer
    mqtt_broker_host: str = Field(default="localhost", env="MQTT_BROKER_HOST")
    mqtt_broker_port: int = Field(default=1883, env="MQTT_BROKER_PORT")
    mqtt_username: str | None = Field(default=None, env="MQTT_USERNAME")
    mqtt_password: str | None = Field(default=None, env="MQTT_PASSWORD")
    mqtt_protocol: str = Field(default="v311", env="MQTT_PROTOCOL")
    auto_create_db: bool = Field(default=True, env="AUTO_CREATE_DB")
    auto_seed_godowns: bool = Field(default=True, env="AUTO_SEED_GODOWNS")
    auto_seed_cameras_from_edge: bool = Field(default=True, env="AUTO_SEED_CAMERAS_FROM_EDGE")
    enable_mqtt_consumer: bool = Field(default=True, env="ENABLE_MQTT_CONSUMER")
    edge_config_path: str | None = Field(default=None, env="EDGE_CONFIG_PATH")
    smtp_host: str | None = Field(default=None, env="SMTP_HOST")
    smtp_port: int | None = Field(default=None, env="SMTP_PORT")
    smtp_user: str | None = Field(default=None, env="SMTP_USER")
    smtp_password: str | None = Field(default=None, env="SMTP_PASSWORD")
    smtp_from: str | None = Field(default=None, env="SMTP_FROM")
    # Twilio messaging / WhatsApp account
    TWILIO_MSG_ACCOUNT_SID: str | None = Field(default=None, env="TWILIO_MSG_ACCOUNT_SID")
    TWILIO_MSG_AUTH_TOKEN: str | None = Field(default=None, env="TWILIO_MSG_AUTH_TOKEN")
    TWILIO_WHATSAPP_FROM: str | None = Field(default=None, env="TWILIO_WHATSAPP_FROM")
    # Twilio voice account
    TWILIO_VOICE_ACCOUNT_SID: str | None = Field(default=None, env="TWILIO_VOICE_ACCOUNT_SID")
    TWILIO_VOICE_AUTH_TOKEN: str | None = Field(default=None, env="TWILIO_VOICE_AUTH_TOKEN")
    TWILIO_VOICE_FROM: str | None = Field(default=None, env="TWILIO_VOICE_FROM")
    TWILIO_VOICE_WEBHOOK_URL: str | None = Field(default=None, env="TWILIO_VOICE_WEBHOOK_URL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()


def get_app_env() -> str:
    raw = os.getenv("PDS_ENV") or os.getenv("APP_ENV") or "dev"
    env = raw.strip().lower()
    if env not in {"dev", "prod"}:
        logging.getLogger("config").warning("Unknown PDS_ENV=%s; defaulting to dev", raw)
        env = "dev"
    return env


def _auth_disabled() -> bool:
    return os.getenv("PDS_AUTH_DISABLED", "true").lower() in {"1", "true", "yes"}


def _is_weak_token(token: str | None) -> bool:
    if not token:
        return True
    token = token.strip()
    if len(token) < 20:
        return True
    weak = {"demo-token", "change-me", "change-me-strong-token", "changeme", "password", "admin"}
    return token.lower() in weak


def validate_runtime_settings() -> None:
    env = get_app_env()
    logger = logging.getLogger("config")

    auth_disabled = _auth_disabled()
    token = os.getenv("PDS_AUTH_TOKEN")
    jwt_secret = (os.getenv("PDS_JWT_SECRET") or token or "").strip()
    admin_password = (os.getenv("PDS_ADMIN_PASSWORD") or "").strip()
    if env == "prod":
        if auth_disabled:
            raise RuntimeError("PDS_AUTH_DISABLED must be false in prod.")
        if _is_weak_token(token):
            raise RuntimeError("PDS_AUTH_TOKEN must be set to a strong value in prod.")
        if len(jwt_secret) < 20:
            raise RuntimeError("PDS_JWT_SECRET must be set to a strong value in prod.")
        if not admin_password:
            raise RuntimeError("PDS_ADMIN_PASSWORD must be set in prod.")
    else:
        if not auth_disabled and _is_weak_token(token):
            logger.warning("PDS_AUTH_TOKEN is weak or missing; dev fallback will be used.")
        if not auth_disabled and len(jwt_secret) < 20:
            logger.warning("PDS_JWT_SECRET is weak or missing; dev fallback will be used.")

    # Provider validation: log and fail-safe to log providers when missing config.
    provider = (os.getenv("WHATSAPP_PROVIDER") or "").lower().strip()
    http_url = (os.getenv("WHATSAPP_HTTP_URL") or os.getenv("WHATSAPP_WEBHOOK_URL") or "").strip()
    if provider in {"http", "meta"} and not http_url:
        logger.error("WHATSAPP_PROVIDER=%s but WHATSAPP_HTTP_URL missing; disabling WhatsApp provider.", provider)
        os.environ["WHATSAPP_PROVIDER"] = "log"
    if provider == "twilio":
        missing = []
        if not (os.getenv("TWILIO_MSG_ACCOUNT_SID") or os.getenv("TWILIO_ACCOUNT_SID")):
            missing.append("TWILIO_MSG_ACCOUNT_SID/TWILIO_ACCOUNT_SID")
        if not (os.getenv("TWILIO_MSG_AUTH_TOKEN") or os.getenv("TWILIO_AUTH_TOKEN")):
            missing.append("TWILIO_MSG_AUTH_TOKEN/TWILIO_AUTH_TOKEN")
        if not os.getenv("TWILIO_WHATSAPP_FROM"):
            missing.append("TWILIO_WHATSAPP_FROM")
        if missing:
            logger.error("Twilio WhatsApp enabled but missing %s; disabling WhatsApp provider.", ", ".join(missing))
            os.environ["WHATSAPP_PROVIDER"] = "log"

    if env == "prod":
        smtp_host = os.getenv("SMTP_HOST") or ""
        if not smtp_host:
            logger.error("SMTP_HOST missing in prod; email provider will be disabled.")

        # Voice provider sanity (CallLogProvider will be used if missing).
        call_from = os.getenv("TWILIO_CALL_FROM_NUMBER") or os.getenv("TWILIO_VOICE_FROM")
        if call_from:
            if not (os.getenv("TWILIO_VOICE_ACCOUNT_SID") or os.getenv("TWILIO_ACCOUNT_SID")):
                logger.error("TWILIO_CALL_FROM_NUMBER set but account SID missing; call provider disabled.")
            if not (os.getenv("TWILIO_VOICE_AUTH_TOKEN") or os.getenv("TWILIO_AUTH_TOKEN")):
                logger.error("TWILIO_CALL_FROM_NUMBER set but auth token missing; call provider disabled.")

        def _env_true(name: str, default: str = "false") -> bool:
            return os.getenv(name, default).lower() in {"1", "true", "yes"}

        if _env_true("AUTO_CREATE_DB", "true"):
            logger.warning("AUTO_CREATE_DB is enabled in prod. Consider setting it to false.")
        if _env_true("AUTO_SEED_GODOWNS", "true"):
            logger.warning("AUTO_SEED_GODOWNS is enabled in prod. Consider setting it to false.")
        if _env_true("AUTO_SEED_CAMERAS_FROM_EDGE", "true"):
            logger.warning("AUTO_SEED_CAMERAS_FROM_EDGE is enabled in prod. Consider setting it to false.")
        if _env_true("AUTO_SEED_RULES", "true"):
            logger.warning("AUTO_SEED_RULES is enabled in prod. Consider setting it to false.")
        if _env_true("ENABLE_MQTT_CONSUMER", "true"):
            logger.warning("ENABLE_MQTT_CONSUMER is enabled in prod. Enable only if required.")
        if _env_true("ENABLE_DISPATCH_WATCHDOG", "true"):
            logger.warning("ENABLE_DISPATCH_WATCHDOG is enabled in prod. Enable only if required.")
        if _env_true("ENABLE_DISPATCH_PLAN_SYNC", "true"):
            logger.warning("ENABLE_DISPATCH_PLAN_SYNC is enabled in prod. Enable only if required.")


validate_runtime_settings()
