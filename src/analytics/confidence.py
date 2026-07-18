"""Transparent confidence composition without an opaque aggregate score."""

from __future__ import annotations

from typing import Mapping

from .contracts import ConfidenceValue

COMPONENTS = (
    "event_timing_confidence",
    "player_identity_confidence",
    "contact_confidence",
    "trajectory_confidence",
    "speed_confidence",
    "stroke_side_confidence",
    "contact_mode_confidence",
    "spin_family_confidence",
    "tactical_shape_confidence",
    "hitting_hand_confidence",
)


def validate_confidence_components(
    values: Mapping[str, ConfidenceValue],
) -> dict[str, ConfidenceValue]:
    """Validate names and preserve each auditable confidence component."""
    unexpected = set(values) - set(COMPONENTS)
    if unexpected:
        raise ValueError(f"unknown confidence components: {sorted(unexpected)}")
    return dict(values)
