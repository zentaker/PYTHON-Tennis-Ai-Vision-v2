from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class PlatformSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TENNISAI_", env_file=".env", extra="ignore")

    app_name: str = "TennisAI Session Platform"
    api_version: str = "v1"
    database_url: str = "postgresql+psycopg://tennisai:tennisai@localhost:5432/tennisai"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_bucket: str = "tennisai-local"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_presign_expires_seconds: int = 900
    max_video_bytes: int = 2_000_000_000
    cors_origins: str = "http://localhost:5173"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> PlatformSettings:
    return PlatformSettings()
