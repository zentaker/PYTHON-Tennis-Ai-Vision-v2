from __future__ import annotations

from .enums import AnalysisRunStatus
from .errors import PlatformError


_TRANSITIONS: dict[AnalysisRunStatus, frozenset[AnalysisRunStatus]] = {
    AnalysisRunStatus.PENDING: frozenset({AnalysisRunStatus.QUEUED, AnalysisRunStatus.CANCELLED}),
    AnalysisRunStatus.QUEUED: frozenset({AnalysisRunStatus.RUNNING, AnalysisRunStatus.CANCELLED}),
    AnalysisRunStatus.RUNNING: frozenset(
        {
            AnalysisRunStatus.QUEUED,
            AnalysisRunStatus.COMPLETE,
            AnalysisRunStatus.PARTIAL,
            AnalysisRunStatus.FAILED,
            AnalysisRunStatus.CANCELLED,
        }
    ),
}


def allowed_analysis_transitions(status: AnalysisRunStatus) -> frozenset[AnalysisRunStatus]:
    return _TRANSITIONS.get(status, frozenset())


def can_transition_analysis(current: AnalysisRunStatus, target: AnalysisRunStatus) -> bool:
    return target in allowed_analysis_transitions(current)


def require_analysis_transition(
    current: AnalysisRunStatus, target: AnalysisRunStatus
) -> None:
    if not can_transition_analysis(current, target):
        raise PlatformError(
            409,
            "ANALYSIS_INVALID_TRANSITION",
            "analysis run transition is not allowed",
            {"current": current.value, "target": target.value},
        )
