from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..domain.enums import AnalysisRunStatus, IntegrityStatus, ProcessingProfile, SessionStatus, Surface, VideoContentType

SHA256_PATTERN = r"^[0-9a-fA-F]{64}$"
FINGERPRINT_PATTERN = r"^[0-9a-fA-F]+$"


class VideoSummary(BaseModel):
    id: UUID
    display_name: str
    content_type: VideoContentType
    size_bytes: int
    sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    integrity_status: IntegrityStatus


class SessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    processing_profile: ProcessingProfile = ProcessingProfile.STANDARD
    surface: Surface = Surface.UNKNOWN


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    status: SessionStatus
    processing_profile: ProcessingProfile
    surface: Surface
    video: VideoSummary | None = None
    latest_analysis_run: "AnalysisRunSummary | None" = None
    bundle_fingerprint: str | None = Field(default=None, pattern=FINGERPRINT_PATTERN)
    created_at: datetime
    updated_at: datetime


class SessionPage(BaseModel):
    items: list[SessionResponse]
    next_cursor: str | None = None


class AnalysisRunSummary(BaseModel):
    id: UUID
    status: AnalysisRunStatus
    processing_profile: ProcessingProfile
    bundle_fingerprint: str | None = Field(default=None, pattern=FINGERPRINT_PATTERN)


SessionResponse.model_rebuild()
