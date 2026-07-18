"""Homography projection and metric court-region classification."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .schemas import FootAnchor, CourtPosition


class CourtProjector:
    def __init__(self, homography_path: Path):
        payload = json.loads(homography_path.read_text(encoding="utf-8"))
        self.h = np.asarray(payload["H_pixel_to_court"], dtype=np.float64)

    def project(self, anchor: FootAnchor) -> CourtPosition:
        q = self.h @ np.array([anchor.x_pixel, anchor.y_pixel, 1.0])
        x, y = q[:2] / q[2]
        return CourtPosition(
            anchor.frame_id,
            anchor.track_id,
            float(x),
            float(y),
            anchor.confidence,
            float(y + 11.885),
            float(11.885 - y),
            bool(-5.485 <= x <= 5.485 and -11.885 <= y <= 11.885),
            bool(y < -11.885),
            bool(y > 11.885),
            bool(x < -5.485),
            bool(x > 5.485),
        )
