from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from ..db.models import SessionRecord, Video
from ..db.repositories.videos import get_source_video, get_video
from ..storage.interface import ObjectStorage, PresignedObject


def create_media_download(
    db: Session, storage: ObjectStorage, session: SessionRecord, video_id: UUID | None = None
) -> tuple[Video, PresignedObject]:
    video = get_video(db, session, video_id) if video_id else get_source_video(db, session)
    if not video:
        raise LookupError("source video not found")
    return video, storage.create_presigned_download(video.object_key, video.content_type)
