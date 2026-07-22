from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import SessionRecord, Video
from ..storage.interface import ObjectStorage, PresignedObject


def create_media_download(
    db: Session, storage: ObjectStorage, session: SessionRecord, video_id: UUID | None = None
) -> tuple[Video, PresignedObject]:
    statement = select(Video).where(Video.session_id == session.id)
    if video_id:
        statement = statement.where(Video.id == video_id)
    video = db.scalar(statement.order_by(Video.created_at.desc()))
    if not video:
        raise LookupError("source video not found")
    return video, storage.create_presigned_download(video.object_key, video.content_type)
