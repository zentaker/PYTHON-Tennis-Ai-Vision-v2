from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query

from ...schemas.session import SessionCreate, SessionPage, SessionResponse
from ...domain.enums import SessionStatus
from ...services.sessions import create_session, get_session, list_sessions
from ..dependencies import db
from ..errors import error_responses, not_found

router = APIRouter(prefix="/api/v1/sessions")


def _response(record):
    video = record.videos[0] if getattr(record, "videos", None) else None
    video_summary = (
        {
            "id": video.id,
            "display_name": video.display_name,
            "content_type": video.content_type,
            "size_bytes": video.size_bytes,
            "sha256": video.sha256,
            "integrity_status": video.integrity_status,
        }
        if video
        else None
    )
    latest = None
    if record.latest_analysis_run_id:
        latest_record = next(
            (run for run in record.analysis_runs if run.id == record.latest_analysis_run_id), None
        )
        latest = (
            {
                "id": latest_record.id,
                "status": latest_record.status,
                "processing_profile": latest_record.processing_profile,
                "bundle_fingerprint": latest_record.bundle_fingerprint,
            }
            if latest_record
            else None
        )
    return {
        "id": record.id,
        "title": record.title,
        "status": record.status,
        "processing_profile": record.processing_profile,
        "surface": record.surface,
        "video": video_summary,
        "latest_analysis_run": latest,
        "bundle_fingerprint": record.bundle_fingerprint,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


@router.post(
    "",
    response_model=SessionResponse,
    status_code=201,
    tags=["Sessions"],
    operation_id="createSession",
    summary="Create a session",
    description="Create metadata for a new analysis session before uploading its source video.",
    responses={
        **error_responses("VALIDATION_ERROR"),
        201: {
            "description": "Session created",
            "content": {"application/json": {"example": {"status": "DRAFT"}}},
        },
    },
)
def create(
    payload: SessionCreate = Body(
        ...,
        openapi_examples={
            "standard": {
                "summary": "Standard session",
                "value": {
                    "title": "Madrid practice",
                    "processing_profile": "STANDARD",
                    "surface": "unknown",
                },
            }
        },
    ),
    database: Any = Depends(db),
):
    return _response(
        create_session(database, payload.title, payload.processing_profile, payload.surface)
    )


@router.get(
    "",
    response_model=SessionPage,
    tags=["Sessions"],
    operation_id="listSessions",
    summary="List sessions",
    description="List sessions in creation order with an opaque cursor for pagination.",
    responses={
        **error_responses("INVALID_CURSOR", "VALIDATION_ERROR"),
        200: {
            "description": "Session page",
            "content": {"application/json": {"example": {"items": [], "next_cursor": None}}},
        },
    },
)
def list_all(
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = None,
    status: SessionStatus | None = None,
    order: str = Query("newest", pattern="^(newest|oldest)$"),
    database: Any = Depends(db),
):
    records, next_cursor = list_sessions(database, limit, cursor, status, order)
    return {"items": [_response(record) for record in records], "next_cursor": next_cursor}


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    tags=["Sessions"],
    operation_id="getSession",
    summary="Get a session",
    description="Return session metadata and the source-video summary when available.",
    responses={
        **error_responses("SESSION_NOT_FOUND", "VALIDATION_ERROR"),
        200: {
            "description": "Session metadata",
            "content": {"application/json": {"example": {"status": "DRAFT"}}},
        },
    },
)
def get(session_id: UUID, database: Any = Depends(db)):
    record = get_session(database, session_id)
    if not record:
        raise not_found("session not found")
    return _response(record)
