from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PlatformSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TENNISAI_", env_file=".env", extra="ignore")

    app_name: str = "TennisAI Session Platform"
    api_version: str = "v1"
    database_url: str = "postgresql+psycopg://tennisai:tennisai@localhost:5432/tennisai"
    s3_internal_endpoint_url: str = "http://localhost:9000"
    s3_public_endpoint_url: str = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_bucket: str = "tennisai-local"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_presign_expires_seconds: int = 900
    max_video_bytes: int = 2_000_000_000
    cors_origins: str = "http://localhost:5173"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    @field_validator("s3_internal_endpoint_url", "s3_public_endpoint_url")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("S3 endpoint must use http/https and include a hostname")
        return value.rstrip("/")

    @field_validator("s3_public_endpoint_url")
    @classmethod
    def reject_internal_public_host(cls, value: str) -> str:
        if urlparse(value).hostname == "minio":
            raise ValueError("public S3 endpoint must not use the internal minio hostname")
        return value

    @field_validator("s3_presign_expires_seconds")
    @classmethod
    def validate_expiration(cls, value: int) -> int:
        if not 1 <= value <= 86_400:
            raise ValueError("presign expiration must be positive and no more than 86400 seconds")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> PlatformSettings:
    return PlatformSettings()
