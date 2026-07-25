from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AnalysisRun, SessionRecord


ACTIVE_STATUSES = ("PENDING", "QUEUED", "RUNNING")


def get_run(db: Session, run_id: UUID, *, for_update: bool = False) -> AnalysisRun | None:
    statement = select(AnalysisRun).where(AnalysisRun.id == run_id)
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def list_runs(db: Session, session_id: UUID) -> list[AnalysisRun]:
    return list(
        db.scalars(
            select(AnalysisRun)
            .where(AnalysisRun.session_id == session_id)
            .order_by(AnalysisRun.created_at.desc())
        )
    )


def get_active_run(
    db: Session, session_id: UUID, processing_profile: str
) -> AnalysisRun | None:
    return db.scalar(
        select(AnalysisRun).where(
            AnalysisRun.session_id == session_id,
            AnalysisRun.processing_profile == processing_profile,
            AnalysisRun.status.in_(ACTIVE_STATUSES),
        )
    )


def get_idempotent_run(
    db: Session, session_id: UUID, idempotency_key: str
) -> AnalysisRun | None:
    return db.scalar(
        select(AnalysisRun).where(
            AnalysisRun.session_id == session_id,
            AnalysisRun.idempotency_key == idempotency_key,
        )
    )


def has_active_run(db: Session, session_id: UUID) -> bool:
    return db.scalar(
        select(AnalysisRun.id).where(
            AnalysisRun.session_id == session_id,
            AnalysisRun.status.in_(ACTIVE_STATUSES),
        ).limit(1)
    ) is not None


def get_expired_running(db: Session, now: datetime) -> list[AnalysisRun]:
    return list(
        db.scalars(
            select(AnalysisRun)
            .where(
                AnalysisRun.status == "RUNNING",
                AnalysisRun.lease_expires_at.is_not(None),
                AnalysisRun.lease_expires_at <= now,
            )
            .order_by(AnalysisRun.lease_expires_at, AnalysisRun.created_at)
            .with_for_update(skip_locked=True)
        )
    )


def get_next_queued(db: Session) -> AnalysisRun | None:
    statement = (
        select(AnalysisRun)
        .where(AnalysisRun.status == "QUEUED")
        .order_by(AnalysisRun.queued_at, AnalysisRun.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return db.scalar(statement)


def get_session(db: Session, session_id: UUID) -> SessionRecord | None:
    return db.scalar(select(SessionRecord).where(SessionRecord.id == session_id))
