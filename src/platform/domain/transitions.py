from __future__ import annotations

from .enums import SessionStatus

_TRANSITIONS: dict[SessionStatus, frozenset[SessionStatus]] = {
    SessionStatus.DRAFT: frozenset({SessionStatus.AWAITING_UPLOAD}),
    SessionStatus.AWAITING_UPLOAD: frozenset({SessionStatus.UPLOADING}),
    SessionStatus.UPLOADING: frozenset({SessionStatus.UPLOADED}),
    SessionStatus.UPLOADED: frozenset({SessionStatus.QUEUED}),
    SessionStatus.QUEUED: frozenset({SessionStatus.PROCESSING}),
    SessionStatus.PROCESSING: frozenset(
        {SessionStatus.COMPLETE, SessionStatus.PARTIAL, SessionStatus.FAILED}
    ),
}


def allowed_session_transitions(status: SessionStatus) -> frozenset[SessionStatus]:
    return _TRANSITIONS.get(status, frozenset())


def can_transition(current: SessionStatus, target: SessionStatus) -> bool:
    return target in allowed_session_transitions(current)


def require_transition(current: SessionStatus, target: SessionStatus) -> None:
    if not can_transition(current, target):
        raise ValueError(f"invalid session transition: {current} -> {target}")
