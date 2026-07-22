from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...domain.enums import AnalysisRunStatus
from ..base import Base


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (Index("ix_analysis_runs_session_id", "session_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=AnalysisRunStatus.PENDING.value)
    processing_profile: Mapped[str] = mapped_column(String(80), default="STANDARD")
    core_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    bundle_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    session = relationship("SessionRecord", back_populates="analysis_runs")
    artifacts = relationship("Artifact", back_populates="analysis_run")
