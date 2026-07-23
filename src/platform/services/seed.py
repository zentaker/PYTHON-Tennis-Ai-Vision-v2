from __future__ import annotations

from sqlalchemy import select

from ..config.settings import get_settings
from ..db.models import SessionRecord
from ..db.session import make_session_factory

STAGE1B_SESSION = "nivel_a2_01"
STAGE1B_FINGERPRINT = "1c0bd683ea349b682be852d02fe7917bea181d8daad42aa97737578d8ceb8009"


def seed_stage1b_reference() -> dict[str, object]:
    settings = get_settings()
    factory = make_session_factory(settings)
    with factory() as db:
        record = db.scalar(select(SessionRecord).where(SessionRecord.title == STAGE1B_SESSION))
        if record is None:
            record = SessionRecord(
                title=STAGE1B_SESSION,
                status="PARTIAL",
                processing_profile="STANDARD",
                surface="unknown",
                bundle_fingerprint=STAGE1B_FINGERPRINT,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
        return {
            "session_id": record.id,
            "title": record.title,
            "status": record.status,
            "bundle_fingerprint": record.bundle_fingerprint,
            "idempotent": True,
        }
