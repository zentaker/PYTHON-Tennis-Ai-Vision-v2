from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UploadInitiate(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)
    content_type: str
    size_bytes: int = Field(gt=0)
    sha256: str | None = Field(default=None, min_length=64, max_length=64)


class UploadResponse(BaseModel):
    video_id: UUID
    object_key: str
    upload_url: str
    method: str
    required_headers: dict[str, str]
    expires_at: datetime


class UploadComplete(BaseModel):
    size_bytes: int = Field(gt=0)
    content_type: str
    sha256: str | None = Field(default=None, min_length=64, max_length=64)


class UploadCompleteResponse(BaseModel):
    video_id: UUID
    status: str
    integrity_status: str


class MediaResponse(BaseModel):
    download_url: str
    expires_at: datetime
    content_type: str
    size_bytes: int
    sha256: str | None
    integrity_status: str
