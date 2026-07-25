from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..domain.enums import AnalysisRunStatus, ProcessingProfile


class AnalysisRunCreate(BaseModel):
    session_id: UUID
    processing_profile: ProcessingProfile = ProcessingProfile.STANDARD
    max_attempts: int = Field(default=3, ge=1, le=10)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class AnalysisRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    input_video_id: UUID | None
    status: AnalysisRunStatus
    processing_profile: ProcessingProfile
    idempotency_key: str | None
    attempt: int
    max_attempts: int
    queued_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    terminal_at: datetime | None
    worker_version: str | None
    bundle_fingerprint: str | None
    result_manifest: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    cancel_requested_at: datetime | None


class AnalysisRunList(BaseModel):
    items: list[AnalysisRunResponse]


class CancelAnalysisRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=200)
