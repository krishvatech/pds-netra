from __future__ import annotations

from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_PATH, override=False)


class Settings(BaseSettings):
    database_url: str = Field(
        default="postgresql+psycopg2://digitalnetra:digitalnetra@127.0.0.1:55432/digital-netra",
        env="DATABASE_URL",
    )
    jwt_secret: str = Field(default="change-me", env="JWT_SECRET")
    jwt_exp_minutes: int = Field(default=720, env="JWT_EXP_MINUTES")
    app_env: str = Field(default="dev", env="APP_ENV")
    cors_origins: str = Field(
        default="http://localhost:3001,http://127.0.0.1:3001",
        env="CORS_ORIGINS",
    )
    live_dir: str = Field(default="data/live", env="PDS_LIVE_DIR")
    live_stale_threshold_sec: int = Field(default=30, env="PDS_LIVE_STALE_THRESHOLD_SEC")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
