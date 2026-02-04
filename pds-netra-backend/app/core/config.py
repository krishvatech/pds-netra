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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
