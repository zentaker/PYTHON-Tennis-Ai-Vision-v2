from __future__ import annotations

from enum import StrEnum


class SessionStatus(StrEnum):
    DRAFT = "DRAFT"
    AWAITING_UPLOAD = "AWAITING_UPLOAD"
    UPLOADING = "UPLOADING"
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class AnalysisRunStatus(StrEnum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ProcessingProfile(StrEnum):
    FAST = "FAST"
    STANDARD = "STANDARD"
    TACTICAL = "TACTICAL"


class Surface(StrEnum):
    CLAY = "clay"
    HARD = "hard"
    GRASS = "grass"
    CARPET = "carpet"
    UNKNOWN = "unknown"


class VideoContentType(StrEnum):
    MP4 = "video/mp4"
    QUICKTIME = "video/quicktime"


class VideoRole(StrEnum):
    SOURCE = "SOURCE"


class IntegrityStatus(StrEnum):
    CLIENT_DECLARED = "CLIENT_DECLARED"
    STORAGE_VERIFIED = "STORAGE_VERIFIED"
    HASH_VERIFIED = "HASH_VERIFIED"
    FAILED = "FAILED"


class ArtifactKind(StrEnum):
    SOURCE_VIDEO = "SOURCE_VIDEO"
    ANALYSIS_BUNDLE = "ANALYSIS_BUNDLE"
    MANIFEST = "MANIFEST"
    SESSION = "SESSION"
    RALLIES = "RALLIES"
    EVENTS = "EVENTS"
    BALL_TRACK = "BALL_TRACK"
    COURT_MAP = "COURT_MAP"
    METRICS = "METRICS"
    CLIP = "CLIP"
    THUMBNAIL = "THUMBNAIL"
    REPORT = "REPORT"
