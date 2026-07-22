from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...schemas.analysis_run import AnalysisRunResponse, ArtifactResponse
from ...schemas.upload import MediaResponse
from ...services.media import create_media_download
from ...services.sessions import get_session
from ..dependencies import db, storage
from ..errors import not_found

router = APIRouter(prefix="/api/v1/sessions/{session_id}", tags=["media"])


@router.get("/media", response_model=MediaResponse)
def media(session_id: UUID, database: Session = Depends(db), object_storage=Depends(storage)):
    session = get_session(database, session_id)
    if not session:
        raise not_found("session not found")
    try:
        video, presigned = create_media_download(database, object_storage, session)
    except LookupError as exc:
        raise not_found(str(exc)) from exc
    return {
        "download_url": presigned.url,
        "expires_at": presigned.expires_at,
        "content_type": video.content_type,
        "size_bytes": video.size_bytes,
        "sha256": video.sha256,
        "integrity_status": video.integrity_status,
    }


@router.get("/analysis-runs", response_model=list[AnalysisRunResponse])
def analysis_runs(session_id: UUID, database: Session = Depends(db)):
    session = get_session(database, session_id)
    if not session:
        raise not_found("session not found")
    return session.analysis_runs


@router.get("/artifacts", response_model=list[ArtifactResponse])
def artifacts(session_id: UUID, database: Session = Depends(db)):
    session = get_session(database, session_id)
    if not session:
        raise not_found("session not found")
    return [artifact for run in session.analysis_runs for artifact in run.artifacts]
