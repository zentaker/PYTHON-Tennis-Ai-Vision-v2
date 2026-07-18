"""Priority-based support-point extraction with airborne uncertainty."""

from __future__ import annotations

from .schemas import BoundingBox, FootAnchor, PlayerPose


class FootAnchorSmoother:
    """Causal moving average that preserves airborne and fallback warnings."""

    def __init__(self, window: int = 3):
        if window < 1:
            raise ValueError("foot smoothing window must be positive")
        self.window = window
        self._history: dict[str, list[tuple[float, float]]] = {}

    def update(self, anchor: FootAnchor) -> FootAnchor:
        values = self._history.setdefault(anchor.track_id, [])
        values.append((anchor.x_pixel, anchor.y_pixel))
        del values[: -self.window]
        x = sum(item[0] for item in values) / len(values)
        y = sum(item[1] for item in values) / len(values)
        return FootAnchor(
            anchor.frame_id,
            anchor.track_id,
            x,
            y,
            anchor.method,
            anchor.confidence,
            anchor.airborne_possible,
            anchor.fallback_used,
            anchor.support_side,
            anchor.low_confidence,
            anchor.occluded,
            len(values) > 1,
        )


def foot_anchor(
    frame_id: int, track_id: str, bbox: BoundingBox, pose: PlayerPose | None = None
) -> FootAnchor:
    points = pose.by_name() if pose else {}
    for names, method in (
        (
            (
                "left_heel",
                "right_heel",
                "left_toe",
                "right_toe",
                "left_big_toe",
                "right_big_toe",
                "left_small_toe",
                "right_small_toe",
            ),
            "pose_heel-toe",
        ),
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
                min(item.confidence for item in valid) < 0.5,
                False,
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
        True,
        True,
    )
