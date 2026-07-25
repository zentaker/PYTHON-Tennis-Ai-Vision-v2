from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...domain.enums import IntegrityStatus, VideoRole
from ..base import Base


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (
        Index("ix_videos_session_id", "session_id"),
        Index("ix_videos_sha256", "sha256"),
        UniqueConstraint("session_id", "role", name="uq_videos_session_role"),
        UniqueConstraint("object_key", name="uq_videos_object_key"),
        CheckConstraint("role IN ('SOURCE')", name="ck_videos_role"),
        CheckConstraint(
            "integrity_status IN ('CLIENT_DECLARED', 'STORAGE_VERIFIED', 'HASH_VERIFIED', 'FAILED')",
            name="ck_videos_integrity_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(24), default=VideoRole.SOURCE.value)
    display_name: Mapped[str] = mapped_column(String(255))
    object_key: Mapped[str] = mapped_column(String(1024), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    integrity_status: Mapped[str] = mapped_column(
        String(32), default=IntegrityStatus.CLIENT_DECLARED.value
    )
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)
    encoded_width: Mapped[int | None] = mapped_column(nullable=True)
    encoded_height: Mapped[int | None] = mapped_column(nullable=True)
    canonical_width: Mapped[int | None] = mapped_column(nullable=True)
    canonical_height: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    session = relationship("SessionRecord", back_populates="videos", foreign_keys=[session_id])
