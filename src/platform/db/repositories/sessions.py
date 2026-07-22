from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from ..models import SessionRecord


def get_session(db: Session, session_id):
    statement: Select = (
        select(SessionRecord)
        .options(selectinload(SessionRecord.videos), selectinload(SessionRecord.analysis_runs))
        .where(SessionRecord.id == session_id)
    )
    return db.scalar(statement)


def list_sessions(db: Session, statement, limit: int) -> list[SessionRecord]:
    return list(db.scalars(statement.limit(limit + 1)).all())
