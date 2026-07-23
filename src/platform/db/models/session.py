from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...domain.enums import SessionStatus
from ..base import Base


class SessionRecord(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_status", "status"),
        Index("ix_sessions_created_at", "created_at"),
        Index("ix_sessions_source_video_id", "source_video_id"),
        Index("ix_sessions_latest_analysis_run_id", "latest_analysis_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), default=SessionStatus.DRAFT.value)
    processing_profile: Mapped[str] = mapped_column(String(80), default="STANDARD")
    surface: Mapped[str] = mapped_column(String(20), default="unknown")
    source_video_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "videos.id", name="fk_sessions_source_video_id", ondelete="SET NULL", use_alter=True
        ),
        nullable=True,
    )
    latest_analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "analysis_runs.id",
            name="fk_sessions_latest_analysis_run_id",
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
    )
    bundle_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    analysis_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    analysis_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    videos = relationship("Video", back_populates="session", foreign_keys="Video.session_id")
    analysis_runs = relationship(
        "AnalysisRun", back_populates="session", foreign_keys="AnalysisRun.session_id"
    )
