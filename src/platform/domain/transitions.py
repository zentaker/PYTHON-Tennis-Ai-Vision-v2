from __future__ import annotations

from .enums import SessionStatus
from .errors import PlatformError

_TRANSITIONS: dict[SessionStatus, frozenset[SessionStatus]] = {
    SessionStatus.DRAFT: frozenset({SessionStatus.AWAITING_UPLOAD}),
    SessionStatus.AWAITING_UPLOAD: frozenset({SessionStatus.UPLOADING}),
    SessionStatus.UPLOADING: frozenset({SessionStatus.UPLOADED}),
    SessionStatus.UPLOADED: frozenset({SessionStatus.QUEUED}),
    SessionStatus.QUEUED: frozenset({SessionStatus.PROCESSING}),
    SessionStatus.PROCESSING: frozenset(
        {
            SessionStatus.COMPLETE,
            SessionStatus.PARTIAL,
            SessionStatus.FAILED,
            SessionStatus.QUEUED,
        }
    ),
    SessionStatus.COMPLETE: frozenset({SessionStatus.QUEUED}),
    SessionStatus.PARTIAL: frozenset({SessionStatus.QUEUED}),
    SessionStatus.FAILED: frozenset({SessionStatus.QUEUED}),
}


def allowed_session_transitions(status: SessionStatus) -> frozenset[SessionStatus]:
    return _TRANSITIONS.get(status, frozenset())


def can_transition(current: SessionStatus, target: SessionStatus) -> bool:
    return target in allowed_session_transitions(current)


def require_transition(current: SessionStatus, target: SessionStatus) -> None:
    if not can_transition(current, target):
        raise PlatformError(
            409,
            "INVALID_SESSION_STATE",
            f"invalid session transition: {current} -> {target}",
            {"current": current.value, "target": target.value},
        )
