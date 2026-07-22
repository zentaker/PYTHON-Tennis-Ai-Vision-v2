from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..domain.enums import SessionStatus


class VideoSummary(BaseModel):
    id: UUID
    display_name: str
    content_type: str
    size_bytes: int
    sha256: str | None
    integrity_status: str


class SessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    processing_profile: str = Field(default="STANDARD", min_length=1, max_length=80)
    surface: str = Field(default="unknown", max_length=20)


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    status: SessionStatus
    processing_profile: str
    surface: str
    video: VideoSummary | None = None
    latest_analysis_run: "AnalysisRunSummary | None" = None
    bundle_fingerprint: str | None = None
    created_at: datetime
    updated_at: datetime


class SessionPage(BaseModel):
    items: list[SessionResponse]
    next_cursor: str | None = None


class AnalysisRunSummary(BaseModel):
    id: UUID
    status: str
    processing_profile: str
    bundle_fingerprint: str | None = None


SessionResponse.model_rebuild()
