from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends

from ...schemas.analysis_run import AnalysisRunResponse, ArtifactResponse
from ...schemas.upload import MediaResponse
from ...services.media import create_media_download
from ...services.runs import get_analysis_runs, get_artifacts
from ...services.sessions import get_session
from ..dependencies import db, storage
from ..errors import ERROR_RESPONSES, not_found

router = APIRouter(prefix="/api/v1/sessions/{session_id}")


@router.get(
    "/media",
    response_model=MediaResponse,
    tags=["Media"],
    operation_id="getSessionMedia",
    summary="Get session media",
    description="Return a short-lived presigned download URL for the session source video.",
    responses={
        **ERROR_RESPONSES,
        200: {
            "description": "Presigned media URL",
            "content": {
                "application/json": {
                    "example": {
                        "download_url": "https://storage.example/object",
                        "integrity_status": "STORAGE_VERIFIED",
                    }
                }
            },
        },
    },
)
def media(session_id: UUID, database: Any = Depends(db), object_storage=Depends(storage)):
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


@router.get(
    "/analysis-runs",
    response_model=list[AnalysisRunResponse],
    tags=["Analysis Runs"],
    operation_id="listAnalysisRuns",
    summary="List analysis runs",
    description="List analysis-run metadata for a session.",
    responses={
        **ERROR_RESPONSES,
        200: {"description": "Analysis runs", "content": {"application/json": {"example": []}}},
    },
)
def analysis_runs(session_id: UUID, database: Any = Depends(db)):
    session = get_session(database, session_id)
    if not session:
        raise not_found("session not found")
    return [
        {
            "id": run.id,
            "session_id": run.session_id,
            "status": run.status,
            "processing_profile": run.processing_profile,
            "core_version": run.core_version,
            "bundle_fingerprint": run.bundle_fingerprint,
            "created_at": run.created_at,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
        }
        for run in get_analysis_runs(database, session)
    ]


@router.get(
    "/artifacts",
    response_model=list[ArtifactResponse],
    tags=["Artifacts"],
    operation_id="listArtifacts",
    summary="List session artifacts",
    description="List analysis bundle artifacts linked to the session's analysis runs.",
    responses={
        **ERROR_RESPONSES,
        200: {"description": "Artifacts", "content": {"application/json": {"example": []}}},
    },
)
def artifacts(session_id: UUID, database: Any = Depends(db)):
    session = get_session(database, session_id)
    if not session:
        raise not_found("session not found")
    return [
        {
            "id": artifact.id,
            "analysis_run_id": artifact.analysis_run_id,
            "kind": artifact.kind,
            "object_key": artifact.object_key,
            "media_type": artifact.media_type,
            "schema_version": artifact.schema_version,
            "size_bytes": artifact.size_bytes,
            "sha256": artifact.sha256,
            "created_at": artifact.created_at,
        }
        for artifact in get_artifacts(database, session)
    ]
