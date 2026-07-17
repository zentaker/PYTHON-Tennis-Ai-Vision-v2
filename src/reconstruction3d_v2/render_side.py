"""Metric Y/Z side view with visible baselines and exterior zones."""

from __future__ import annotations

import cv2
import numpy as np


def world_to_canvas(
    y: float, z: float, *, width: int = 1100, height: int = 600, margin: int = 80
) -> tuple[int, int]:
    scale = min((width - 2 * margin) / 27.77, (height - 2 * margin) / 7.0)
    return int(round(width / 2 + y * scale)), int(round(height - margin - z * scale))


def canvas_to_world(
    px: float, py: float, *, width: int = 1100, height: int = 600, margin: int = 80
) -> tuple[float, float]:
    scale = min((width - 2 * margin) / 27.77, (height - 2 * margin) / 7.0)
    return (float(px - width / 2) / scale, float(height - margin - py) / scale)


def draw_side(
    points: list[tuple[float, float]],
    current: tuple[float, float] | None = None,
    *,
    label: str = "",
) -> np.ndarray:
    image = np.full((600, 1100, 3), 28, dtype=np.uint8)
    cv2.rectangle(image, (0, 420), (1100, 599), (45, 45, 75), -1)
    cv2.line(image, world_to_canvas(-11.885, 0), world_to_canvas(11.885, 0), (210, 210, 210), 3)
    cv2.line(image, world_to_canvas(0, 0), world_to_canvas(0, 0.914), (0, 220, 255), 4)
    cv2.line(image, world_to_canvas(-11.885, 0), world_to_canvas(-11.885, 4), (180, 180, 180), 2)
    cv2.line(image, world_to_canvas(11.885, 0), world_to_canvas(11.885, 4), (180, 180, 180), 2)
    if len(points) >= 2:
        cv2.polylines(
            image,
            [np.array([world_to_canvas(y, z) for y, z in points], dtype=np.int32)],
            False,
            (0, 255, 255),
            3,
        )
    if current is not None:
        cv2.circle(image, world_to_canvas(*current), 10, (0, 255, 0), -1)
    for y, text in [
        (-11.885, "NEAR BASELINE -11.885m"),
        (0, "NET Y=0"),
        (11.885, "FAR BASELINE +11.885m"),
    ]:
        cv2.putText(image, text, (world_to_canvas(y, 0)[0] - 80, 450), 0, 0.45, (255, 255, 255), 1)
    cv2.putText(image, "NEAR", (25, 35), 0, 0.8, (255, 255, 255), 2)
    cv2.putText(image, "FAR", (1010, 35), 0, 0.8, (255, 255, 255), 2)
    cv2.putText(image, "Y (m) ->", (510, 575), 0, 0.65, (255, 255, 255), 2)
    cv2.putText(image, "Z (m)", (20, 120), 0, 0.65, (255, 255, 255), 2)
    cv2.putText(image, label, (20, 65), 0, 0.55, (255, 255, 255), 1)
    return image
