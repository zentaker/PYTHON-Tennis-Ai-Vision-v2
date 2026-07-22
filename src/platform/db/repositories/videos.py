from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SessionRecord, Video
from ...domain.enums import VideoRole


def get_video(db: Session, session: SessionRecord, video_id):
    return db.scalar(select(Video).where(Video.id == video_id, Video.session_id == session.id))


def get_source_video(db: Session, session: SessionRecord):
    return db.scalar(
        select(Video)
        .where(Video.session_id == session.id, Video.role == VideoRole.SOURCE.value)
        .order_by(Video.created_at.desc())
    )
