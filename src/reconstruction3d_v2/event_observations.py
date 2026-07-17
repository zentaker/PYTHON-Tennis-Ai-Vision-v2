"""Strict event-pixel extraction for the anchored v2 model."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class EventObservation:
    event_id: str
    selected_frame: int
    timestamp_seconds: float
    pixel_x: float | None
    pixel_y: float | None
    source: str
    confidence: float | None
    temporal_distance_frames: int
    temporal_distance_seconds: float
    valid: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _direct(rows: list[dict[str, str]], frame: int) -> EventObservation | None:
    row = rows[frame]
    if row.get("x_smooth", "") != "" and row.get("y_smooth", "") != "":
        return EventObservation(
            "",
            frame,
            float(row["timestamp_seconds"]),
            float(row["x_smooth"]),
            float(row["y_smooth"]),
            str(row.get("source", "detected")),
            float(row.get("confidence", 0.0)),
            0,
            0.0,
            True,
            "direct_smooth_observation",
        )
    return None


def observe_event(
    rows: list[dict[str, str]], event: dict[str, Any], frame: int
) -> EventObservation:
    """Use the candidate frame or interpolate only from immediately adjacent ±2 frames."""
    direct = _direct(rows, frame)
    if direct is not None:
        return EventObservation(
            str(event["id"]),
            direct.selected_frame,
            direct.timestamp_seconds,
            direct.pixel_x,
            direct.pixel_y,
            direct.source,
            direct.confidence,
            0,
            0.0,
            True,
            direct.reason,
        )
    candidates: list[tuple[int, dict[str, str]]] = []
    for distance in range(1, 3):
        for candidate in (frame - distance, frame + distance):
            if 0 <= candidate < len(rows) and _direct(rows, candidate) is not None:
                candidates.append((candidate, rows[candidate]))
    if len(candidates) < 2:
        return EventObservation(
            str(event["id"]),
            frame,
            float(rows[frame]["timestamp_seconds"]),
            None,
            None,
            "missing",
            None,
            99,
            99.0,
            False,
            "no_valid_observation_within_two_frames",
        )
    before = max((item for item in candidates if item[0] < frame), default=None)
    after = min((item for item in candidates if item[0] > frame), default=None)
    if before is None or after is None:
        return EventObservation(
            str(event["id"]),
            frame,
            float(rows[frame]["timestamp_seconds"]),
            None,
            None,
            "missing",
            None,
            99,
            99.0,
            False,
            "interpolation_requires_both_adjacent_sides",
        )
    t0, t1 = float(before[1]["timestamp_seconds"]), float(after[1]["timestamp_seconds"])
    t = float(rows[frame]["timestamp_seconds"])
    alpha = (t - t0) / (t1 - t0)
    x = float(before[1]["x_smooth"]) + alpha * (
        float(after[1]["x_smooth"]) - float(before[1]["x_smooth"])
    )
    y = float(before[1]["y_smooth"]) + alpha * (
        float(after[1]["y_smooth"]) - float(before[1]["y_smooth"])
    )
    return EventObservation(
        str(event["id"]),
        frame,
        t,
        x,
        y,
        "interpolated_event",
        min(float(before[1]["confidence"]), float(after[1]["confidence"])),
        max(frame - before[0], after[0] - frame),
        max(frame - before[0], after[0] - frame) * 0.016667,
        True,
        "temporal_interpolation_within_two_frames",
    )


def audit_events(
    rows: list[dict[str, str]], events: list[dict[str, Any]], frame_map: dict[str, int]
) -> list[EventObservation]:
    return [observe_event(rows, event, int(frame_map[str(event["id"])])) for event in events]
