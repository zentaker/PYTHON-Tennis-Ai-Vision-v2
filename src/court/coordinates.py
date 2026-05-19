"""Court coordinate conventions for calibration.

The project coordinate system uses meters:
- origin (0, 0): center of the net
- X axis: along the net, positive to the near player's right
- Y axis: perpendicular to the net, negative on the near side and positive on the far side
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal


CalibrationLayout = Literal["doubles", "singles"]
PointName = Literal[
    "far_left",
    "far_right",
    "near_left",
    "near_right",
    "far_left_service",
    "far_right_service",
    "near_left_service",
    "near_right_service",
]

CALIBRATION_POINT_ORDER: tuple[PointName, ...] = (
    "far_left",
    "far_right",
    "near_left",
    "near_right",
    "far_left_service",
    "far_right_service",
    "near_left_service",
    "near_right_service",
)


@dataclass(frozen=True)
class CourtDimensions:
    """ITF tennis court dimensions used by the project."""

    total_length_m: float = 23.77
    half_length_m: float = 11.885
    singles_width_m: float = 8.23
    doubles_width_m: float = 10.97
    service_line_distance_m: float = 6.40

    @property
    def singles_half_width_m(self) -> float:
        return self.singles_width_m / 2.0

    @property
    def doubles_half_width_m(self) -> float:
        return self.doubles_width_m / 2.0


COURT_DIMENSIONS = CourtDimensions()


def calibration_court_points(layout: CalibrationLayout = "doubles") -> MappingProxyType[str, tuple[float, float]]:
    """Return the 8 court calibration points in meters for the selected layout.

    The four service-box auxiliary points always use singles sidelines. The four outer
    court corners use doubles or singles width depending on the selected layout.
    """
    dimensions = COURT_DIMENSIONS
    if layout == "doubles":
        corner_x = dimensions.doubles_half_width_m
    elif layout == "singles":
        corner_x = dimensions.singles_half_width_m
    else:
        raise ValueError(f"Unsupported calibration layout: {layout}")

    service_x = dimensions.singles_half_width_m
    baseline_y = dimensions.half_length_m
    service_y = dimensions.service_line_distance_m

    points = {
        "far_left": (-corner_x, baseline_y),
        "far_right": (corner_x, baseline_y),
        "near_left": (-corner_x, -baseline_y),
        "near_right": (corner_x, -baseline_y),
        "far_left_service": (-service_x, service_y),
        "far_right_service": (service_x, service_y),
        "near_left_service": (-service_x, -service_y),
        "near_right_service": (service_x, -service_y),
    }
    return MappingProxyType(points)
