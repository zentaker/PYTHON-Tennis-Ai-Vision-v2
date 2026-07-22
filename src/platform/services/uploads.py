from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config.settings import PlatformSettings
from ..db.models import SessionRecord, Video
from ..domain.enums import IntegrityStatus, SessionStatus, VideoRole
from ..storage.interface import ObjectStorage, PresignedObject
from ..storage.keys import source_video_key
from .sessions import transition_session

ALLOWED_MEDIA_TYPES = {"video/mp4": ".mp4", "video/quicktime": ".mov"}


def validate_upload(
    display_name: str, content_type: str, size_bytes: int, settings: PlatformSettings
) -> None:
    if content_type not in ALLOWED_MEDIA_TYPES:
        raise ValueError("unsupported content type")
    suffix = display_name.lower().rsplit(".", 1)[-1] if "." in display_name else ""
    if f".{suffix}" != ALLOWED_MEDIA_TYPES[content_type]:
        raise ValueError("filename extension does not match content type")
    if size_bytes <= 0 or size_bytes > settings.max_video_bytes:
        raise ValueError("video size exceeds configured limit")


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
    existing = db.scalar(
        select(Video).where(Video.session_id == session.id, Video.role == VideoRole.SOURCE.value)
    )
    if existing:
        raise ValueError("session already has an active source video")
    video = Video(
        session_id=session.id,
        role=VideoRole.SOURCE.value,
        display_name=display_name,
        object_key=source_video_key(session.id, uuid4(), display_name),
        content_type=content_type,
        size_bytes=size_bytes,
        sha256=sha256,
        integrity_status=IntegrityStatus.CLIENT_DECLARED.value,
    )
    db.add(video)
    if session.status == SessionStatus.DRAFT.value:
        session.status = SessionStatus.AWAITING_UPLOAD.value
    transition_session(db, session, SessionStatus.UPLOADING)
    session.source_video_id = video.id
    db.commit()
    db.refresh(video)
    return video, storage.create_presigned_upload(video.object_key, content_type)


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
    video = db.scalar(select(Video).where(Video.id == video_id, Video.session_id == session.id))
    if not video:
        raise LookupError("video not found")
    validate_upload(video.display_name, content_type, size_bytes, settings)
    if content_type != video.content_type or size_bytes != video.size_bytes:
        raise ValueError("upload metadata does not match initiation")
    try:
        head = storage.head_object(video.object_key)
    except (KeyError, OSError) as exc:
        video.integrity_status = IntegrityStatus.FAILED.value
        db.commit()
        raise ValueError("storage object is not present") from exc
    if head.size_bytes != size_bytes or (head.content_type and head.content_type != content_type):
        video.integrity_status = IntegrityStatus.FAILED.value
        db.commit()
        raise ValueError("storage object does not match declared upload")
    video.sha256 = sha256 or video.sha256
    video.integrity_status = IntegrityStatus.STORAGE_VERIFIED.value
    session.status = SessionStatus.UPLOADED.value
    db.commit()
    db.refresh(video)
    return video
