from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends

from ...schemas.upload import UploadComplete, UploadCompleteResponse, UploadInitiate, UploadResponse
from ...services.sessions import get_session
from ...services.uploads import complete_upload, initiate_upload
from ..dependencies import db, settings, storage
from ..errors import ERROR_RESPONSES, invalid, not_found

router = APIRouter(prefix="/api/v1/sessions/{session_id}/uploads")


@router.post(
    "",
    response_model=UploadResponse,
    status_code=201,
    tags=["Uploads"],
    operation_id="initiateVideoUpload",
    summary="Initiate a video upload",
    description="Validate source-video metadata and return a short-lived presigned PUT URL.",
    responses={
        **ERROR_RESPONSES,
        201: {
            "description": "Presigned upload URL",
            "content": {
                "application/json": {"example": {"method": "PUT", "object_key": "sessions/..."}}
            },
        },
    },
)
def initiate(
    session_id: UUID,
    payload: UploadInitiate = Body(
        ...,
        openapi_examples={
            "mp4": {
                "summary": "MP4 source video",
                "value": {
                    "display_name": "rally.mp4",
                    "content_type": "video/mp4",
                    "size_bytes": 1048576,
                },
            }
        },
    ),
    database: Any = Depends(db),
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


@router.post(
    "/{video_id}/complete",
    response_model=UploadCompleteResponse,
    tags=["Uploads"],
    operation_id="completeVideoUpload",
    summary="Complete a video upload",
    description="HEAD the object in MinIO/S3 and mark it STORAGE_VERIFIED when metadata matches.",
    responses={
        **ERROR_RESPONSES,
        200: {
            "description": "Upload verified",
            "content": {
                "application/json": {
                    "example": {"status": "UPLOADED", "integrity_status": "STORAGE_VERIFIED"}
                }
            },
        },
    },
)
def complete(
    session_id: UUID,
    video_id: UUID,
    payload: UploadComplete = Body(
        ...,
        openapi_examples={
            "uploaded": {
                "summary": "Uploaded object metadata",
                "value": {"size_bytes": 1048576, "content_type": "video/mp4"},
            }
        },
    ),
    database: Any = Depends(db),
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
