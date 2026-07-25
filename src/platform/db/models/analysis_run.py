from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...domain.enums import AnalysisRunStatus
from ..base import Base


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        Index("ix_analysis_runs_session_id", "session_id"),
        Index("ix_analysis_runs_queue", "status", "queued_at"),
        Index(
            "uq_analysis_runs_active_profile",
            "session_id",
            "processing_profile",
            unique=True,
            postgresql_where=text("status IN ('PENDING', 'QUEUED', 'RUNNING')"),
            sqlite_where=text("status IN ('PENDING', 'QUEUED', 'RUNNING')"),
        ),
        Index(
            "uq_analysis_runs_active_session",
            "session_id",
            unique=True,
            postgresql_where=text("status IN ('PENDING', 'QUEUED', 'RUNNING')"),
            sqlite_where=text("status IN ('PENDING', 'QUEUED', 'RUNNING')"),
        ),
        CheckConstraint(
            "attempt >= 0 AND max_attempts >= 1 AND attempt <= max_attempts",
            name="ck_analysis_runs_attempt_bounds",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'QUEUED', 'RUNNING', 'COMPLETE', 'PARTIAL', 'FAILED', 'CANCELLED')",
            name="ck_analysis_runs_status",
        ),
        Index(
            "uq_analysis_runs_idempotency_key",
            "session_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
            sqlite_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    input_video_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("videos.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default=AnalysisRunStatus.PENDING.value)
    processing_profile: Mapped[str] = mapped_column(String(80), default="STANDARD")
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    request_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=3)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_acquired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    worker_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    core_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    bundle_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    result_manifest: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    session = relationship(
        "SessionRecord", back_populates="analysis_runs", foreign_keys=[session_id]
    )
    input_video = relationship("Video", foreign_keys=[input_video_id])
    artifacts = relationship("Artifact", back_populates="analysis_run")
