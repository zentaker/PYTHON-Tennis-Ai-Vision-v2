"""Versioned, immutable contracts for analytics records."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Any, Mapping


class StrokeSide(StrEnum):
    SERVE = "serve"
    FOREHAND = "forehand"
    BACKHAND = "backhand"
    OVERHEAD = "overhead"
    UNKNOWN = "unknown"


class ContactMode(StrEnum):
    SERVE = "serve"
    RETURN = "return"
    GROUNDSTROKE = "groundstroke"
    VOLLEY = "volley"
    HALF_VOLLEY = "half_volley"
    OVERHEAD = "overhead"
    UNKNOWN = "unknown"


class SpinFamily(StrEnum):
    FLAT = "flat"
    TOPSPIN = "topspin"
    SLICE = "slice"
    UNKNOWN = "unknown"


class TacticalShape(StrEnum):
    DRIVE = "drive"
    DROP = "drop"
    LOB = "lob"
    APPROACH = "approach"
    PASSING_SHOT = "passing_shot"
    DEFENSIVE = "defensive"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class HittingHand(StrEnum):
    LEFT = "left"
    RIGHT = "right"
    UNKNOWN = "unknown"


def _confidence(value: float) -> float:
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    return value


def _json_value(value: Any) -> Any:
    """Convert immutable Python containers to JSON-native values."""
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class ConfidenceValue:
    source: str
    method: str
    confidence: float
    warnings: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    human_labeled: bool = False
    model_inferred: bool = False
    geometry_derived: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "confidence", _confidence(self.confidence))


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    source: str
    method: str
    description: str
    confidence: float
    human_labeled: bool = False
    model_inferred: bool = False
    geometry_derived: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "confidence", _confidence(self.confidence))


@dataclass(frozen=True, slots=True)
class AnalyticsEventInput:
    event_id: str
    timestamp_seconds: float
    frame_id: int | None = None
    legacy_shot_type: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BallTrajectorySample:
    timestamp_seconds: float
    x: float
    y: float
    z: float | None = None
    coordinate_unit: str = "pixels"
    observed_or_interpolated: str = "observed"
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if self.coordinate_unit not in {"pixels", "metres"}:
            raise ValueError("coordinate_unit must be pixels or metres")
        object.__setattr__(self, "confidence", _confidence(self.confidence))


@dataclass(frozen=True, slots=True)
class PlayerContextSample:
    timestamp_seconds: float
    track_id: str
    identity: str
    x_m: float | None = None
    y_m: float | None = None
    confidence: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "confidence", _confidence(self.confidence))


@dataclass(frozen=True, slots=True)
class ContactContext:
    event_id: str
    track_id: str | None = None
    frame_id: int | None = None
    ball_wrist_distance_px: float | None = None
    confidence: ConfidenceValue | None = None


def _unknown_confidence(component: str) -> ConfidenceValue:
    return ConfidenceValue("unavailable", f"{component}_unavailable", 0.0, ("unknown",))


@dataclass(frozen=True, slots=True)
class ClassifiedStroke:
    stroke_side: StrokeSide = StrokeSide.UNKNOWN
    contact_mode: ContactMode = ContactMode.UNKNOWN
    spin_family: SpinFamily = SpinFamily.UNKNOWN
    tactical_shape: TacticalShape = TacticalShape.UNKNOWN
    hitting_hand: HittingHand = HittingHand.UNKNOWN
    stroke_side_confidence: ConfidenceValue = field(
        default_factory=lambda: _unknown_confidence("stroke_side")
    )
    contact_mode_confidence: ConfidenceValue = field(
        default_factory=lambda: _unknown_confidence("contact_mode")
    )
    spin_family_confidence: ConfidenceValue = field(
        default_factory=lambda: _unknown_confidence("spin_family")
    )
    tactical_shape_confidence: ConfidenceValue = field(
        default_factory=lambda: _unknown_confidence("tactical_shape")
    )
    hitting_hand_confidence: ConfidenceValue = field(
        default_factory=lambda: _unknown_confidence("hitting_hand")
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize dimensions as schema-compatible value/confidence pairs."""
        return {
            name: {
                "value": getattr(self, name).value,
                "confidence": _json_value(asdict(getattr(self, f"{name}_confidence"))),
            }
            for name in (
                "stroke_side",
                "contact_mode",
                "spin_family",
                "tactical_shape",
                "hitting_hand",
            )
        }


@dataclass(frozen=True, slots=True)
class BallKinematics:
    status: str
    method: str
    speed_unit: str
    incoming_status: str = "unavailable"
    outgoing_status: str = "unavailable"
    incoming_speed_mps: float | None = None
    incoming_speed_kmh: float | None = None
    outgoing_speed_mps: float | None = None
    outgoing_speed_kmh: float | None = None
    peak_outgoing_speed_kmh: float | None = None
    speed_at_net_kmh: float | None = None
    speed_before_bounce_kmh: float | None = None
    speed_after_bounce_kmh: float | None = None
    samples_used: int = 0
    rejected_samples: int = 0
    incoming_samples_used: int = 0
    incoming_rejected_samples: int = 0
    outgoing_samples_used: int = 0
    outgoing_rejected_samples: int = 0
    window_start_seconds: float | None = None
    window_end_seconds: float | None = None
    confidence: float = 0.0
    incoming_confidence: float = 0.0
    outgoing_confidence: float = 0.0
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in {"available", "partial", "unavailable"}:
            raise ValueError("invalid kinematics status")
        for name in ("incoming_status", "outgoing_status"):
            if getattr(self, name) not in {"available", "unavailable"}:
                raise ValueError(f"invalid {name}")
        expected_units = {
            "pixel_apparent": "pixels_per_second",
            "court_planar_xy": "metres_per_second",
            "estimated_3d": "metres_per_second",
        }
        if self.method not in expected_units:
            raise ValueError("invalid kinematics method")
        if self.speed_unit != expected_units[self.method]:
            raise ValueError("speed_unit is inconsistent with method")
        for name in (
            "samples_used",
            "rejected_samples",
            "incoming_samples_used",
            "incoming_rejected_samples",
            "outgoing_samples_used",
            "outgoing_rejected_samples",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for name in (
            "incoming_speed_mps",
            "incoming_speed_kmh",
            "outgoing_speed_mps",
            "outgoing_speed_kmh",
            "peak_outgoing_speed_kmh",
            "speed_at_net_kmh",
            "speed_before_bounce_kmh",
            "speed_after_bounce_kmh",
        ):
            value = getattr(self, name)
            if value is not None and (not isfinite(value) or value < 0):
                raise ValueError(f"{name} must be finite and non-negative")
        for name in ("window_start_seconds", "window_end_seconds"):
            value = getattr(self, name)
            if value is not None and not isfinite(value):
                raise ValueError(f"{name} must be finite")
        if (
            self.window_start_seconds is not None
            and self.window_end_seconds is not None
            and self.window_start_seconds > self.window_end_seconds
        ):
            raise ValueError("window_start_seconds must not exceed window_end_seconds")
        object.__setattr__(self, "confidence", _confidence(self.confidence))
        object.__setattr__(self, "incoming_confidence", _confidence(self.incoming_confidence))
        object.__setattr__(self, "outgoing_confidence", _confidence(self.outgoing_confidence))

    def to_dict(self) -> dict[str, Any]:
        return _json_value(asdict(self))


@dataclass(frozen=True, slots=True)
class StrokeAnalyticsRecord:
    schema_version: str
    event: AnalyticsEventInput
    stroke: ClassifiedStroke
    kinematics: BallKinematics | None = None
    evidence: tuple[EvidenceItem, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event": _json_value(asdict(self.event)),
            "stroke": self.stroke.to_dict(),
            "kinematics": self.kinematics.to_dict() if self.kinematics else None,
            "evidence": [_json_value(asdict(item)) for item in self.evidence],
        }
