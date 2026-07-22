from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...schemas.upload import UploadComplete, UploadInitiate, UploadResponse
from ...services.sessions import get_session
from ...services.uploads import complete_upload, initiate_upload
from ..dependencies import db, settings, storage
from ..errors import invalid, not_found

router = APIRouter(prefix="/api/v1/sessions/{session_id}/uploads", tags=["uploads"])


@router.post("", response_model=UploadResponse, status_code=201)
def initiate(
    session_id: UUID,
    payload: UploadInitiate,
    database: Session = Depends(db),
    platform_settings=Depends(settings),
    object_storage=Depends(storage),
):
    session = get_session(database, session_id)
    if not session:
        raise not_found("session not found")
    try:
        video, presigned = initiate_upload(
            database,
            object_storage,
            platform_settings,
            session,
            payload.display_name,
            payload.content_type,
            payload.size_bytes,
            payload.sha256,
        )
    except (ValueError, OSError) as exc:
        raise invalid(str(exc)) from exc
    return {
        "video_id": video.id,
        "object_key": video.object_key,
        "upload_url": presigned.url,
        "method": presigned.method,
        "required_headers": presigned.headers,
        "expires_at": presigned.expires_at,
    }


@router.post("/{video_id}/complete")
def complete(
    session_id: UUID,
    video_id: UUID,
    payload: UploadComplete,
    database: Session = Depends(db),
    platform_settings=Depends(settings),
    object_storage=Depends(storage),
):
    session = get_session(database, session_id)
    if not session:
        raise not_found("session not found")
    try:
        video = complete_upload(
            database,
            object_storage,
            platform_settings,
            session,
            video_id,
            payload.size_bytes,
            payload.content_type,
            payload.sha256,
        )
    except LookupError as exc:
        raise not_found(str(exc)) from exc
    except (ValueError, OSError) as exc:
        raise invalid(str(exc)) from exc
    return {"video_id": video.id, "status": "UPLOADED", "integrity_status": video.integrity_status}
