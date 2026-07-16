"""Small, JSON-friendly data models used by the Stage 5B pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Observation:
    frame_id: int
    timestamp_seconds: float
    x: float
    y: float
    confidence: float
    source: str
    weight: float


@dataclass
class SegmentFit:
    segment_id: str
    start_event: str
    end_event: str
    start_frame: int
    end_frame: int
    params: np.ndarray
    cost_components: dict[str, float] = field(default_factory=dict)
    status: str = "FIT_MARGINAL"
    warnings: list[str] = field(default_factory=list)
    observations_used: int = 0
    outliers: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def p0(self) -> np.ndarray:
        return self.params[:3]

    @property
    def v0(self) -> np.ndarray:
        return self.params[3:]

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "start_event": self.start_event,
            "end_event": self.end_event,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "P0_m": self.p0.tolist(),
            "V0_m_s": self.v0.tolist(),
            "cost_components": self.cost_components,
            "status": self.status,
            "warnings": self.warnings,
            "observations_used": self.observations_used,
            "outliers": self.outliers,
            "metrics": self.metrics,
        }
