from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Artifact, SessionRecord


def list_artifacts(db: Session, session: SessionRecord):
    return list(
        db.scalars(
            select(Artifact)
            .join(Artifact.analysis_run)
            .where(Artifact.analysis_run.has(session_id=session.id))
            .order_by(Artifact.created_at.desc())
        ).all()
    )
