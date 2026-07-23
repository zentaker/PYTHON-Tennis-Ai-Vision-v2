from __future__ import annotations

import base64
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import SessionRecord
from ..db.repositories.sessions import get_session as repository_get_session
from ..db.repositories.sessions import list_sessions as repository_list_sessions
from ..domain.enums import SessionStatus
from ..domain.errors import PlatformError
from ..domain.transitions import require_transition


def encode_cursor(created_at: datetime, session_id: UUID) -> str:
    value = f"{created_at.isoformat()}|{session_id}"
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        created, identifier = base64.urlsafe_b64decode(padded).decode().split("|", 1)
        return datetime.fromisoformat(created), UUID(identifier)
    except (ValueError, UnicodeDecodeError) as exc:
        raise PlatformError(400, "INVALID_CURSOR", "cursor is invalid") from exc


def create_session(db: Session, title: str, processing_profile: str, surface: str) -> SessionRecord:
    record = SessionRecord(
        title=title,
        processing_profile=processing_profile,
        surface=surface,
        status=SessionStatus.DRAFT.value,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_session(db: Session, session_id: UUID) -> SessionRecord | None:
    return repository_get_session(db, session_id)


def list_sessions(
    db: Session, limit: int, cursor: str | None, status: SessionStatus | None, order: str
) -> tuple[list[SessionRecord], str | None]:
    limit = max(1, min(limit, 100))
    statement = select(SessionRecord)
    if status:
        statement = statement.where(SessionRecord.status == status.value)
    descending = order != "oldest"
    if cursor:
        created_at, session_id = decode_cursor(cursor)
        if descending:
            statement = statement.where(
                (SessionRecord.created_at < created_at)
                | ((SessionRecord.created_at == created_at) & (SessionRecord.id < session_id))
            )
        else:
            statement = statement.where(
                (SessionRecord.created_at > created_at)
                | ((SessionRecord.created_at == created_at) & (SessionRecord.id > session_id))
            )
    if descending:
        statement = statement.order_by(SessionRecord.created_at.desc(), SessionRecord.id.desc())
    else:
        statement = statement.order_by(SessionRecord.created_at.asc(), SessionRecord.id.asc())
    records = repository_list_sessions(db, statement, limit)
    next_cursor = (
        encode_cursor(records[limit - 1].created_at, records[limit - 1].id)
        if len(records) > limit
        else None
    )
    return records[:limit], next_cursor


def transition_session(
    db: Session, record: SessionRecord, target: SessionStatus, *, commit: bool = True
) -> SessionRecord:
    current = SessionStatus(record.status)
    require_transition(current, target)
    record.status = target.value
    record.updated_at = datetime.now(timezone.utc)
    if commit:
        db.commit()
        db.refresh(record)
    return record
