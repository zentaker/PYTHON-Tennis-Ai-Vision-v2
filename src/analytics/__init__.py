"""Deterministic, provider-independent stroke and ball analytics foundations."""

from .contracts import (
    AnalyticsEventInput,
    BallKinematics,
    BallTrajectorySample,
    ClassifiedStroke,
    ConfidenceValue,
    ContactContext,
    EvidenceItem,
    PlayerContextSample,
    StrokeAnalyticsRecord,
)

__all__ = [
    "AnalyticsEventInput",
    "BallKinematics",
    "BallTrajectorySample",
    "ClassifiedStroke",
    "ConfidenceValue",
    "ContactContext",
    "EvidenceItem",
    "PlayerContextSample",
    "StrokeAnalyticsRecord",
]
