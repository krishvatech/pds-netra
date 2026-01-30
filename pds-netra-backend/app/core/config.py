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
    mqtt_protocol: str = Field(default="v311", env="MQTT_PROTOCOL")
    auto_create_db: bool = Field(default=True, env="AUTO_CREATE_DB")
    auto_seed_godowns: bool = Field(default=True, env="AUTO_SEED_GODOWNS")
    auto_seed_cameras_from_edge: bool = Field(default=True, env="AUTO_SEED_CAMERAS_FROM_EDGE")
    enable_mqtt_consumer: bool = Field(default=True, env="ENABLE_MQTT_CONSUMER")
    edge_config_path: str | None = Field(default=None, env="EDGE_CONFIG_PATH")

    # ------------------------------------------------------------------
    # ANPR (CSV-first PoC)
    #
    # Edge writes ANPR events to CSV. Backend reads those CSVs and serves
    # them to the dashboard via an API endpoint.
    #
    # Default location is: <backend-root>/data/anpr_csv/<GODOWN_ID>/*.csv
    #
    # You can override with env: ANPR_CSV_DIR
    # ------------------------------------------------------------------
    anpr_csv_dir: str = Field(default="data/anpr_csv", env="ANPR_CSV_DIR")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
