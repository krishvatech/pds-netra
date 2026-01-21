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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
