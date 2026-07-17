"""Typed, serialisable data contracts for player perception."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def bottom_center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, self.y2)


@dataclass(frozen=True)
class PlayerDetection:
    frame_id: int
    detection_id: str
    bbox: BoundingBox
    class_name: str = "person"


@dataclass(frozen=True)
class PlayerTrack:
    frame_id: int
    track_id: str
    bbox: BoundingBox
    identity: str = "unknown"
    confidence: float = 0.0


@dataclass(frozen=True)
class PoseKeypoint:
    name: str
    x: float
    y: float
    confidence: float
    visible: bool = True


@dataclass(frozen=True)
class PlayerPose:
    frame_id: int
    track_id: str
    keypoints: tuple[PoseKeypoint, ...]
    confidence: float

    def by_name(self) -> dict[str, PoseKeypoint]:
        return {item.name: item for item in self.keypoints}


@dataclass(frozen=True)
class FootAnchor:
    frame_id: int
    track_id: str
    x_pixel: float
    y_pixel: float
    method: str
    confidence: float
    airborne_possible: bool
    fallback_used: bool
    support_side: str = "unknown"


@dataclass(frozen=True)
class CourtPosition:
    frame_id: int
    track_id: str
    x_m: float
    y_m: float
    confidence: float
    distance_to_near_baseline_m: float
    distance_to_far_baseline_m: float
    inside_court: bool
    behind_near_baseline: bool
    behind_far_baseline: bool
    left_outside: bool
    right_outside: bool


@dataclass(frozen=True)
class ContactAudit:
    event_id: str
    expected_player: str
    track_id: str
    frame_id: int
    court_position: CourtPosition | None
    ball_pixel: tuple[float, float] | None
    wrist_pixels: dict[str, tuple[float, float]]
    ball_wrist_distance_px: float | None
    confidence: float
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class FramePerception:
    frame_id: int
    detections: tuple[PlayerDetection, ...]
    tracks: tuple[PlayerTrack, ...]
    poses: tuple[PlayerPose, ...]
    foot_anchors: tuple[FootAnchor, ...]
    court_positions: tuple[CourtPosition, ...]


@dataclass
class PerceptionReport:
    schema_version: str = "1.0"
    clip_id: str = ""
    backend: str = ""
    device: str = "cpu"
    frame_count: int = 0
    frames: list[FramePerception] = field(default_factory=list)
    contacts: list[ContactAudit] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
