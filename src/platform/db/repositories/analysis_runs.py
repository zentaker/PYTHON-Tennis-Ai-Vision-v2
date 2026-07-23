from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AnalysisRun
from ..models import SessionRecord


def list_analysis_runs(db: Session, session: SessionRecord):
    return list(
        db.scalars(
            select(AnalysisRun)
            .where(AnalysisRun.session_id == session.id)
            .order_by(AnalysisRun.created_at.desc())
        ).all()
    )
