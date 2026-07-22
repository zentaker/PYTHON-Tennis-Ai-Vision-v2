from __future__ import annotations

import re
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config.settings import PlatformSettings
from ..db.models import SessionRecord, Video
from ..db.repositories.videos import get_video
from ..domain.enums import IntegrityStatus, SessionStatus, VideoContentType, VideoRole
from ..domain.errors import PlatformError
from ..storage.interface import ObjectStorage, PresignedObject
from ..storage.keys import source_video_key
from .sessions import transition_session

SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
MAX_FILENAME_EXTENSIONS = {
    VideoContentType.MP4.value: ".mp4",
    VideoContentType.QUICKTIME.value: ".mov",
}


def normalize_sha256(value: str | None) -> str | None:
    if value is None:
        return None
    if not SHA256_RE.fullmatch(value):
        raise PlatformError(422, "INVALID_SHA256", "sha256 must be 64 hexadecimal characters")
    return value.lower()


def validate_upload(
    display_name: str, content_type: str, size_bytes: int, settings: PlatformSettings
) -> None:
    if content_type not in MAX_FILENAME_EXTENSIONS:
        raise PlatformError(422, "UNSUPPORTED_VIDEO_CONTENT_TYPE", "unsupported video content type")
    suffix = display_name.lower().rsplit(".", 1)[-1] if "." in display_name else ""
    if f".{suffix}" != MAX_FILENAME_EXTENSIONS[content_type]:
        raise PlatformError(
            422, "VIDEO_EXTENSION_MISMATCH", "filename extension does not match content type"
        )
    if size_bytes <= 0 or size_bytes > settings.max_video_bytes:
        raise PlatformError(413, "VIDEO_SIZE_EXCEEDED", "video size exceeds configured limit")


def initiate_upload(
    db: Session,
    storage: ObjectStorage,
    settings: PlatformSettings,
    session: SessionRecord,
    display_name: str,
    content_type: str,
    size_bytes: int,
    sha256: str | None,
) -> tuple[Video, PresignedObject]:
    validate_upload(display_name, content_type, size_bytes, settings)
    declared_sha = normalize_sha256(sha256)
    if session.status not in {SessionStatus.DRAFT.value, SessionStatus.AWAITING_UPLOAD.value}:
        raise PlatformError(409, "INVALID_SESSION_STATE", "session cannot initiate an upload")
    existing = db.scalar(
        select(Video).where(Video.session_id == session.id, Video.role == VideoRole.SOURCE.value)
    )
    if existing or session.source_video_id is not None:
        raise PlatformError(
            409,
            "SOURCE_VIDEO_ALREADY_EXISTS",
            "session already has a source video",
            {
                "session_source_video_id": str(session.source_video_id)
                if session.source_video_id
                else None,
                "existing_video_id": str(existing.id) if existing else None,
            },
        )
    video_id = uuid4()
    object_key = source_video_key(session.id, video_id, display_name)
    try:
        presigned = storage.create_presigned_upload(object_key, content_type)
    except Exception as exc:
        db.rollback()
        raise PlatformError(
            503, "STORAGE_SIGNING_FAILED", "storage could not sign the upload"
        ) from exc
    video = Video(
        id=video_id,
        session_id=session.id,
        role=VideoRole.SOURCE.value,
        display_name=display_name,
        object_key=object_key,
        content_type=content_type,
        size_bytes=size_bytes,
        sha256=declared_sha,
        integrity_status=IntegrityStatus.CLIENT_DECLARED.value,
    )
    db.add(video)
    try:
        # Materialize the video row before assigning the session pointer so the
        # non-deferrable foreign key remains valid within this one transaction.
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise PlatformError(
            409, "SOURCE_VIDEO_ALREADY_EXISTS", "session already has a source video"
        ) from exc
    if session.status == SessionStatus.DRAFT.value:
        transition_session(db, session, SessionStatus.AWAITING_UPLOAD, commit=False)
    transition_session(db, session, SessionStatus.UPLOADING, commit=False)
    session.source_video_id = video_id
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise PlatformError(
            409, "SOURCE_VIDEO_ALREADY_EXISTS", "session already has a source video"
        ) from exc
    db.refresh(video)
    return video, presigned


def complete_upload(
    db: Session,
    storage: ObjectStorage,
    settings: PlatformSettings,
    session: SessionRecord,
    video_id: UUID,
    size_bytes: int,
    content_type: str,
    sha256: str | None,
) -> Video:
    video = get_video(db, session, video_id)
    if not video:
        raise PlatformError(404, "VIDEO_NOT_FOUND", "video not found")
    validate_upload(video.display_name, content_type, size_bytes, settings)
    declared_sha = normalize_sha256(sha256)
    if video.sha256 and declared_sha and video.sha256 != declared_sha:
        raise PlatformError(
            409, "UPLOAD_SHA_MISMATCH", "initiate and complete sha256 values differ"
        )
    if content_type != video.content_type or size_bytes != video.size_bytes:
        raise PlatformError(
            409, "UPLOAD_METADATA_MISMATCH", "upload metadata does not match initiation"
        )
    if session.status == SessionStatus.UPLOADED.value:
        if video.integrity_status == IntegrityStatus.STORAGE_VERIFIED.value:
            return video
        raise PlatformError(409, "INVALID_SESSION_STATE", "session upload state is inconsistent")
    if session.status != SessionStatus.UPLOADING.value:
        raise PlatformError(409, "INVALID_SESSION_STATE", "session cannot complete an upload")
    try:
        head = storage.head_object(video.object_key)
    except (KeyError, OSError) as exc:
        raise PlatformError(404, "STORAGE_OBJECT_MISSING", "storage object is not present") from exc
    if head.size_bytes != size_bytes or (head.content_type and head.content_type != content_type):
        raise PlatformError(
            409, "STORAGE_OBJECT_MISMATCH", "storage object does not match declared upload"
        )
    video.sha256 = declared_sha or video.sha256
    video.integrity_status = IntegrityStatus.STORAGE_VERIFIED.value
    transition_session(db, session, SessionStatus.UPLOADED, commit=False)
    db.commit()
    db.refresh(video)
    return video
