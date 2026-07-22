from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from ..db.models import SessionRecord, Video
from ..db.repositories.videos import get_source_video, get_video
from ..domain.errors import PlatformError
from ..storage.interface import ObjectStorage, PresignedObject


def create_media_download(
    db: Session, storage: ObjectStorage, session: SessionRecord, video_id: UUID | None = None
) -> tuple[Video, PresignedObject]:
    video = get_video(db, session, video_id) if video_id else get_source_video(db, session)
    if not video:
        raise PlatformError(404, "VIDEO_NOT_FOUND", "source video not found")
    try:
        presigned = storage.create_presigned_download(video.object_key, video.content_type)
    except Exception as exc:
        raise PlatformError(
            503,
            "STORAGE_SIGNING_FAILED",
            "storage could not sign the download",
            {"operation": "download"},
        ) from exc
    return video, presigned
