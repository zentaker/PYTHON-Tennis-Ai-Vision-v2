from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...schemas.session import SessionCreate, SessionPage, SessionResponse
from ...services.sessions import create_session, get_session, list_sessions
from ..dependencies import db
from ..errors import not_found

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def _response(record):
    video = record.videos[0] if getattr(record, "videos", None) else None
    latest = None
    if record.latest_analysis_run_id:
        latest = next(
            (run for run in record.analysis_runs if run.id == record.latest_analysis_run_id), None
        )
    return {
        "id": record.id,
        "title": record.title,
        "status": record.status,
        "processing_profile": record.processing_profile,
        "surface": record.surface,
        "video": video,
        "latest_analysis_run": latest,
        "bundle_fingerprint": record.bundle_fingerprint,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


@router.post("", response_model=SessionResponse, status_code=201)
def create(payload: SessionCreate, database: Session = Depends(db)):
    return _response(
        create_session(database, payload.title, payload.processing_profile, payload.surface)
    )


@router.get("", response_model=SessionPage)
def list_all(
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = None,
    status: str | None = None,
    order: str = Query("newest", pattern="^(newest|oldest)$"),
    database: Session = Depends(db),
):
    records, next_cursor = list_sessions(database, limit, cursor, status, order)
    return {"items": [_response(record) for record in records], "next_cursor": next_cursor}


@router.get("/{session_id}", response_model=SessionResponse)
def get(session_id: UUID, database: Session = Depends(db)):
    record = get_session(database, session_id)
    if not record:
        raise not_found("session not found")
    return _response(record)
