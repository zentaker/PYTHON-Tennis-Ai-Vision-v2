"""Contact evidence aggregation; does not invent a 3-D contact."""

from __future__ import annotations

import math

from .schemas import ContactAudit, CourtPosition, PlayerPose


def audit_contact(
    event: dict,
    track_id: str,
    position: CourtPosition | None,
    pose: PlayerPose | None,
    ball_pixel: tuple[float, float] | None,
) -> ContactAudit:
    wrists = {}
    if pose:
        for name in ("left_wrist", "right_wrist"):
            point = pose.by_name().get(name)
            if point and point.visible:
                wrists[name] = (point.x, point.y)
    distances = (
        [math.dist(ball_pixel, point) for point in wrists.values()] if ball_pixel and wrists else []
    )
    warnings = []
    if not wrists:
        warnings.append("wrist_observation_unavailable")
    if position is None:
        warnings.append("court_position_unavailable")
    return ContactAudit(
        str(event["id"]),
        str(event.get("player", event.get("side", "unknown"))),
        track_id,
        int(event["frame_start"]),
        position,
        ball_pixel,
        wrists,
        min(distances) if distances else None,
        min((pose.confidence if pose else 0.0), position.confidence if position else 0.0),
        tuple(warnings),
    )
