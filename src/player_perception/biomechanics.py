"""Non-clinical geometric pose features with confidence and status."""

from __future__ import annotations

import math

from .schemas import PlayerPose


def _angle(a, b, c):
    u = (a.x - b.x, a.y - b.y)
    v = (c.x - b.x, c.y - b.y)
    den = math.hypot(*u) * math.hypot(*v)
    return (
        math.degrees(math.acos(max(-1.0, min(1.0, (u[0] * v[0] + u[1] * v[1]) / den))))
        if den
        else None
    )


def geometric_features(pose: PlayerPose) -> dict[str, dict[str, float | str | None]]:
    points = pose.by_name()
    result = {}
    for name, triplet in {
        "left_knee_flexion": ("left_hip", "left_knee", "left_ankle"),
        "right_knee_flexion": ("right_hip", "right_knee", "right_ankle"),
        "left_elbow_flexion": ("left_shoulder", "left_elbow", "left_wrist"),
        "right_elbow_flexion": ("right_shoulder", "right_elbow", "right_wrist"),
    }.items():
        values = [points.get(item) for item in triplet]
        angle = _angle(*values) if all(values) else None
        result[name] = {
            "value": angle,
            "confidence": min((point.confidence for point in values if point), default=0.0),
            "status": "VALID" if angle is not None else "MISSING",
        }
    return result
