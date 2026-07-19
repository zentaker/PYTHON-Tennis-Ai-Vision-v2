"""Versioned immutable contracts for Stage 5B v3 candidate samples."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True, slots=True)
class XYZSample:
    frame_id: int
    timestamp_seconds: float
    x_m: float
    y_m: float
    z_m: float
    confidence: float
    observed_or_interpolated: str
    segment_id: str
    event_context: str
    reprojection_error_px: float
    observed_pixel_x: float
    observed_pixel_y: float
    reprojected_pixel_x: float
    reprojected_pixel_y: float
    uncertainty_x_m: float
    uncertainty_y_m: float
    uncertainty_z_m: float
    constraint_sources: tuple[str, ...]
    player_identity: str
    contact_event_id: str | None
    hypothesis_id: str
    ambiguity_status: str
    warnings: tuple[str, ...] = ()
    coordinate_unit: str = "metres"

    def __post_init__(self) -> None:
        if not isinstance(self.frame_id, int) or self.frame_id < 0:
            raise ValueError("frame_id must be a non-negative integer")
        for name in (
            "timestamp_seconds",
            "x_m",
            "y_m",
            "z_m",
            "reprojection_error_px",
            "observed_pixel_x",
            "observed_pixel_y",
            "reprojected_pixel_x",
            "reprojected_pixel_y",
            "uncertainty_x_m",
            "uncertainty_y_m",
            "uncertainty_z_m",
        ):
            if not isfinite(float(getattr(self, name))):
                raise ValueError(f"{name} must be finite")
        if self.z_m < -1e-6:
            raise ValueError("z_m must be non-negative within tolerance")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be in [0,1]")
        if self.observed_or_interpolated not in {"observed", "interpolated"}:
            raise ValueError("invalid observed_or_interpolated")
        if self.player_identity not in {"near", "far", "unknown"}:
            raise ValueError("invalid player_identity")
        if self.ambiguity_status not in {"RESOLVED", "AMBIGUOUS"}:
            raise ValueError("invalid ambiguity_status")
        if self.coordinate_unit != "metres":
            raise ValueError("coordinate_unit must be metres")
        if not self.segment_id or not self.hypothesis_id or not self.constraint_sources:
            raise ValueError("segment, hypothesis, and constraint sources are required")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["constraint_sources"] = list(self.constraint_sources)
        payload["warnings"] = list(self.warnings)
        for key, value in payload.items():
            if isinstance(value, float):
                payload[key] = round(value, 6)
        return payload


def validate_segment_order(samples: list[XYZSample]) -> None:
    previous: dict[str, float] = {}
    for sample in samples:
        if sample.segment_id in previous and sample.timestamp_seconds <= previous[sample.segment_id]:
            raise ValueError(f"timestamps not strictly increasing in {sample.segment_id}")
        previous[sample.segment_id] = sample.timestamp_seconds
