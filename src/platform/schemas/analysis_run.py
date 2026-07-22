from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from ..domain.enums import AnalysisRunStatus, ProcessingProfile


class AnalysisRunResponse(BaseModel):
    id: UUID
    session_id: UUID
    status: AnalysisRunStatus
    processing_profile: ProcessingProfile
    core_version: str | None = None
    bundle_fingerprint: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ArtifactResponse(BaseModel):
    id: UUID
    analysis_run_id: UUID
    kind: str
    object_key: str
    media_type: str
    schema_version: str | None = None
    size_bytes: int
    sha256: str
    created_at: datetime
