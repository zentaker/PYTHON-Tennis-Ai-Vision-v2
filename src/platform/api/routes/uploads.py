from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends

from ...schemas.upload import UploadComplete, UploadCompleteResponse, UploadInitiate, UploadResponse
from ...services.sessions import get_session
from ...services.uploads import complete_upload, initiate_upload
from ..dependencies import db, settings, storage
from ..errors import error_responses, not_found

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
        **error_responses(
            "SESSION_NOT_FOUND",
            "INVALID_SESSION_STATE",
            "SOURCE_VIDEO_ALREADY_EXISTS",
            "VIDEO_SIZE_EXCEEDED",
            "INVALID_SHA256",
            "UNSUPPORTED_VIDEO_CONTENT_TYPE",
            "VIDEO_EXTENSION_MISMATCH",
            "STORAGE_SIGNING_FAILED",
            "VALIDATION_ERROR",
        ),
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
        **error_responses(
            "SESSION_NOT_FOUND",
            "VIDEO_NOT_FOUND",
            "STORAGE_OBJECT_MISSING",
            "INVALID_SESSION_STATE",
            "UPLOAD_METADATA_MISMATCH",
            "UPLOAD_SHA_MISMATCH",
            "STORAGE_OBJECT_MISMATCH",
            "VIDEO_SIZE_EXCEEDED",
            "INVALID_SHA256",
            "UNSUPPORTED_VIDEO_CONTENT_TYPE",
            "VIDEO_EXTENSION_MISMATCH",
            "VALIDATION_ERROR",
        ),
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
    return {"video_id": video.id, "status": "UPLOADED", "integrity_status": video.integrity_status}
