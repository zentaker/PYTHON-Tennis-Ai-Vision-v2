from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        Index("ix_artifacts_analysis_run_id", "analysis_run_id"),
        CheckConstraint(
            "kind IN ('SOURCE_VIDEO', 'ANALYSIS_BUNDLE', 'MANIFEST', 'SESSION', 'RALLIES', 'EVENTS', 'BALL_TRACK', 'COURT_MAP', 'METRICS', 'CLIP', 'THUMBNAIL', 'REPORT')",
            name="ck_artifacts_kind",
        ),
        CheckConstraint("size_bytes > 0", name="ck_artifacts_size_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(40))
    object_key: Mapped[str] = mapped_column(String(1024), unique=True)
    media_type: Mapped[str] = mapped_column(String(100))
    schema_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    analysis_run = relationship("AnalysisRun", back_populates="artifacts")
