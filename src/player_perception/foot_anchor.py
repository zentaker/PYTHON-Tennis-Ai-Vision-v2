"""Priority-based support-point extraction with airborne uncertainty."""

from __future__ import annotations

from .schemas import BoundingBox, FootAnchor, PlayerPose


def foot_anchor(
    frame_id: int, track_id: str, bbox: BoundingBox, pose: PlayerPose | None = None
) -> FootAnchor:
    points = pose.by_name() if pose else {}
    for names, method in (
        (("left_heel", "right_heel", "left_toe", "right_toe"), "pose_heel-toe"),
        (("left_ankle", "right_ankle"), "pose_ankle"),
    ):
        valid = [
            points[name]
            for name in names
            if name in points and points[name].visible and points[name].confidence >= 0.35
        ]
        if valid:
            x = sum(item.x for item in valid) / len(valid)
            y = sum(item.y for item in valid) / len(valid)
            return FootAnchor(
                frame_id,
                track_id,
                x,
                y,
                method,
                min(item.confidence for item in valid),
                False,
                False,
                "both"
                if len(valid) > 1
                else "left"
                if valid[0].name.startswith("left_")
                else "right",
            )
    x, y = bbox.bottom_center
    return FootAnchor(
        frame_id,
        track_id,
        x,
        y,
        "bbox_bottom_center",
        bbox.confidence * 0.6,
        True,
        True,
        "unknown",
    )
