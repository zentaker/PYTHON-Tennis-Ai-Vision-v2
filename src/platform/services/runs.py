from __future__ import annotations

from sqlalchemy.orm import Session

from ..db.models import SessionRecord
from ..db.repositories.analysis_runs import list_analysis_runs as repository_list_analysis_runs
from ..db.repositories.artifacts import list_artifacts as repository_list_artifacts


def get_analysis_runs(db: Session, session: SessionRecord):
    return repository_list_analysis_runs(db, session)


def get_artifacts(db: Session, session: SessionRecord):
    return repository_list_artifacts(db, session)
