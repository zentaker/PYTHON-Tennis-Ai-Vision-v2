from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from ..domain.enums import AnalysisRunStatus, ArtifactKind, ProcessingProfile

SHA256_PATTERN = r"^[0-9a-fA-F]{64}$"
FINGERPRINT_PATTERN = r"^[0-9a-fA-F]+$"


class AnalysisRunResponse(BaseModel):
    id: UUID
    session_id: UUID
    status: AnalysisRunStatus
    processing_profile: ProcessingProfile
    core_version: str | None = None
    bundle_fingerprint: str | None = Field(default=None, pattern=FINGERPRINT_PATTERN)
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ArtifactResponse(BaseModel):
    id: UUID
    analysis_run_id: UUID
    kind: ArtifactKind
    object_key: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    schema_version: str | None = None
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=SHA256_PATTERN)
    created_at: datetime
