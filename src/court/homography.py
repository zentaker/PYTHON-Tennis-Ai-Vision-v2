"""Homography computation for Stage 1 court calibration."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import cv2
import numpy as np

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.court.coordinates import CALIBRATION_POINT_ORDER, CalibrationLayout, calibration_court_points


HOMOGRAPHY_METHOD = "cv2.findHomography(method=0)"
HOMOGRAPHY_METHOD_NOTES = (
    "Standard direct homography solve without RANSAC. The 8 correspondences come from "
    "careful manual clicks, not automatic noisy detections, so rejecting points would hide "
    "annotation errors instead of surfacing them."
)


def load_clicked_points(path: Path) -> tuple[dict[str, tuple[float, float]], CalibrationLayout]:
    """Load browser-clicked calibration points from JSON."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_points = payload["court_corners_pixel"]
    layout = payload.get("layout", "doubles")
    if layout not in ("doubles", "singles"):
        raise ValueError(f"Unsupported layout in {path}: {layout}")

    points = {
        name: (float(raw_points[name][0]), float(raw_points[name][1]))
        for name in CALIBRATION_POINT_ORDER
    }
    return points, layout


def ordered_points(points: Mapping[str, tuple[float, float]]) -> np.ndarray:
    """Return points ordered as CALIBRATION_POINT_ORDER."""
    return np.array([points[name] for name in CALIBRATION_POINT_ORDER], dtype=np.float64)


def compute_homography(
    corners_pixel: Mapping[str, tuple[float, float]],
    corners_court: Mapping[str, tuple[float, float]],
) -> np.ndarray:
    """Compute H mapping pixel coordinates (u, v) to court meters (X, Y)."""
    src = ordered_points(corners_pixel)
    dst = ordered_points(corners_court)
    homography, _mask = cv2.findHomography(src, dst, method=0)
    if homography is None:
        raise RuntimeError("cv2.findHomography failed")
    return homography.astype(np.float64)


def apply_homography(homography: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Apply a 3x3 homography to Nx2 points."""
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("points must have shape Nx2")
    homogeneous = np.column_stack([points, np.ones(points.shape[0], dtype=np.float64)])
    projected = homogeneous @ homography.T
    return projected[:, :2] / projected[:, 2:3]


def reprojection_errors_pixels(
    homography_pixel_to_court: np.ndarray,
    corners_pixel: Mapping[str, tuple[float, float]],
    corners_court: Mapping[str, tuple[float, float]],
) -> np.ndarray:
    """Measure round-trip court->pixel error for calibration points in pixels."""
    inverse_h = np.linalg.inv(homography_pixel_to_court)
    court_points = ordered_points(corners_court)
    expected_pixels = ordered_points(corners_pixel)
    projected_pixels = apply_homography(inverse_h, court_points)
    return np.linalg.norm(projected_pixels - expected_pixels, axis=1)


def compute_and_write_homography(
    corners_path: Path,
    output_path: Path,
) -> dict[str, object]:
    """Compute homography from clicked points and persist it as JSON."""
    corners_pixel, layout = load_clicked_points(corners_path)
    corners_court = dict(calibration_court_points(layout))
    homography = compute_homography(corners_pixel, corners_court)
    pixel_errors = reprojection_errors_pixels(homography, corners_pixel, corners_court)

    payload: dict[str, object] = {
        "H_pixel_to_court": homography.tolist(),
        "court_corners_pixel": {
            name: [float(corners_pixel[name][0]), float(corners_pixel[name][1])]
            for name in CALIBRATION_POINT_ORDER
        },
        "court_corners_court_meters": {
            name: [float(corners_court[name][0]), float(corners_court[name][1])]
            for name in CALIBRATION_POINT_ORDER
        },
        "court_mode": layout,
        "method": HOMOGRAPHY_METHOD,
        "method_notes": HOMOGRAPHY_METHOD_NOTES,
        "reprojection_error_pixels_mean": float(pixel_errors.mean()),
        "reprojection_error_pixels_max": float(pixel_errors.max()),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corners", type=Path, default=Path("data/reference_clip/court_corners_pixel.json"))
    parser.add_argument("--output", type=Path, default=Path("data/reference_clip/homography.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = compute_and_write_homography(args.corners, args.output)
    print(f"Homography written to {args.output}")
    print(f"mean_px={payload['reprojection_error_pixels_mean']:.6f}")
    print(f"max_px={payload['reprojection_error_pixels_max']:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
