"""Metric top-view canvas (isotropic X/Y scale, FAR up)."""

from __future__ import annotations

import cv2
import numpy as np

COURT = {"doubles_half": 5.485, "singles_half": 4.115, "baseline": 11.885, "service": 6.40}


def world_to_canvas(
    x: float, y: float, *, width: int = 900, height: int = 1200, margin: int = 70
) -> tuple[int, int]:
    scale = min(
        (width - 2 * margin) / (2 * COURT["doubles_half"] + 2),
        (height - 2 * margin) / (2 * COURT["baseline"] + 2),
    )
    return int(round(width / 2 + x * scale)), int(round(height / 2 - y * scale))


def canvas_to_world(
    px: float, py: float, *, width: int = 900, height: int = 1200, margin: int = 70
) -> tuple[float, float]:
    scale = min(
        (width - 2 * margin) / (2 * COURT["doubles_half"] + 2),
        (height - 2 * margin) / (2 * COURT["baseline"] + 2),
    )
    return (float(px - width / 2) / scale, float(height / 2 - py) / scale)


def draw_top(
    points: list[tuple[float, float]],
    current: tuple[float, float] | None = None,
    *,
    label: str = "",
) -> np.ndarray:
    image = np.full((1200, 900, 3), 28, dtype=np.uint8)

    def line(x1, y1, x2, y2, color, thickness=2):
        cv2.line(image, world_to_canvas(x1, y1), world_to_canvas(x2, y2), color, thickness)

    line(
        -COURT["doubles_half"],
        -COURT["baseline"],
        COURT["doubles_half"],
        -COURT["baseline"],
        (255, 255, 255),
        3,
    )
    line(
        -COURT["doubles_half"],
        COURT["baseline"],
        COURT["doubles_half"],
        COURT["baseline"],
        (255, 255, 255),
        3,
    )
    line(
        -COURT["doubles_half"],
        -COURT["baseline"],
        -COURT["doubles_half"],
        COURT["baseline"],
        (255, 255, 255),
        3,
    )
    line(
        COURT["doubles_half"],
        -COURT["baseline"],
        COURT["doubles_half"],
        COURT["baseline"],
        (255, 255, 255),
        3,
    )
    line(
        -COURT["singles_half"],
        -COURT["baseline"],
        -COURT["singles_half"],
        COURT["baseline"],
        (180, 180, 180),
        2,
    )
    line(
        COURT["singles_half"],
        -COURT["baseline"],
        COURT["singles_half"],
        COURT["baseline"],
        (180, 180, 180),
        2,
    )
    line(-COURT["doubles_half"], 0, COURT["doubles_half"], 0, (0, 220, 255), 4)
    line(
        -COURT["doubles_half"],
        -COURT["service"],
        COURT["doubles_half"],
        -COURT["service"],
        (130, 210, 130),
        2,
    )
    line(
        -COURT["doubles_half"],
        COURT["service"],
        COURT["doubles_half"],
        COURT["service"],
        (130, 210, 130),
        2,
    )
    if len(points) >= 2:
        cv2.polylines(
            image,
            [np.array([world_to_canvas(x, y) for x, y in points], dtype=np.int32)],
            False,
            (0, 255, 255),
            3,
        )
    if current is not None:
        cv2.circle(image, world_to_canvas(*current), 10, (0, 255, 0), -1)
    cv2.putText(image, "FAR", (20, 35), 0, 0.8, (255, 255, 255), 2)
    cv2.putText(image, "NEAR", (20, 1180), 0, 0.8, (255, 255, 255), 2)
    cv2.putText(image, "X (m)", (790, 600), 0, 0.7, (255, 255, 255), 2)
    cv2.putText(image, label, (20, 65), 0, 0.55, (255, 255, 255), 1)
    return image
