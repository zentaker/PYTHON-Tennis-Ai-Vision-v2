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


def load_clicked_payload(path: Path) -> dict[str, object]:
    """Load the complete browser-clicked calibration payload."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_clicked_points(path: Path) -> tuple[dict[str, tuple[float, float]], CalibrationLayout]:
    """Load browser-clicked calibration points from JSON."""
    payload = load_clicked_payload(path)
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


def orientation_validation(
    corners_pixel: Mapping[str, tuple[float, float]],
    frame_width: int,
    frame_height: int,
) -> dict[str, object]:
    """Validate the canonical horizontal frame and far/near, left/right ordering."""
    all_points_in_bounds = all(
        0.0 <= x < frame_width and 0.0 <= y < frame_height
        for x, y in corners_pixel.values()
    )
    far_above_near = all(
        corners_pixel[far_name][1] < corners_pixel[near_name][1]
        for far_name, near_name in (
            ("far_left", "near_left"),
            ("far_right", "near_right"),
            ("far_left_service", "near_left_service"),
            ("far_right_service", "near_right_service"),
        )
    )
    left_before_right = all(
        corners_pixel[left_name][0] < corners_pixel[right_name][0]
        for left_name, right_name in (
            ("far_left", "far_right"),
            ("near_left", "near_right"),
            ("far_left_service", "far_right_service"),
            ("near_left_service", "near_right_service"),
        )
    )
    canonical_horizontal = frame_width > frame_height
    passed = all_points_in_bounds and far_above_near and left_before_right and canonical_horizontal
    return {
        "frame_width": frame_width,
        "frame_height": frame_height,
        "canonical_horizontal": canonical_horizontal,
        "all_points_in_bounds": all_points_in_bounds,
        "far_above_near": far_above_near,
        "left_before_right": left_before_right,
        "passed": passed,
    }


def compute_and_write_homography(
    corners_path: Path,
    output_path: Path,
    *,
    frame_path: Path | None = None,
    clip_id: str | None = None,
) -> dict[str, object]:
    """Compute homography from clicked points and persist it as JSON."""
    clicked_payload = load_clicked_payload(corners_path)
    corners_pixel, layout = load_clicked_points(corners_path)
    corners_court = dict(calibration_court_points(layout))
    homography = compute_homography(corners_pixel, corners_court)
    inverse_h = np.linalg.inv(homography)
    pixel_errors = reprojection_errors_pixels(homography, corners_pixel, corners_court)
    projected_court = apply_homography(homography, ordered_points(corners_pixel))
    court_errors = np.linalg.norm(projected_court - ordered_points(corners_court), axis=1)

    resolved_frame_path = frame_path
    if resolved_frame_path is None and clicked_payload.get("image_path"):
        resolved_frame_path = Path(str(clicked_payload["image_path"]))

    frame_dimensions: dict[str, int] | None = None
    orientation: dict[str, object] | None = None
    if resolved_frame_path is not None:
        frame = cv2.imread(str(resolved_frame_path))
        if frame is None:
            raise FileNotFoundError(f"Could not open calibration frame: {resolved_frame_path}")
        frame_height, frame_width = frame.shape[:2]
        frame_dimensions = {"width": int(frame_width), "height": int(frame_height)}
        orientation = orientation_validation(corners_pixel, int(frame_width), int(frame_height))
        if not orientation["passed"]:
            raise ValueError(f"Calibration orientation validation failed: {orientation}")

    per_point_errors = [
        {
            "point": name,
            "court_to_pixel_error_pixels": float(pixel_errors[index]),
            "pixel_to_court_error_meters": float(court_errors[index]),
        }
        for index, name in enumerate(CALIBRATION_POINT_ORDER)
    ]

    payload: dict[str, object] = {
        "H_pixel_to_court": homography.tolist(),
        "H_court_to_pixel": inverse_h.tolist(),
        "court_corners_pixel": {
            name: [float(corners_pixel[name][0]), float(corners_pixel[name][1])]
            for name in CALIBRATION_POINT_ORDER
        },
        "court_corners_court_meters": {
            name: [float(corners_court[name][0]), float(corners_court[name][1])]
            for name in CALIBRATION_POINT_ORDER
        },
        "court_mode": layout,
        "layout": layout,
        "method": HOMOGRAPHY_METHOD,
        "method_notes": HOMOGRAPHY_METHOD_NOTES,
        "clip_id": clip_id,
        "frame_path": str(resolved_frame_path) if resolved_frame_path is not None else None,
        "frame_dimensions": frame_dimensions,
        "orientation_validation": orientation,
        "reprojection_errors_per_point": per_point_errors,
        "reprojection_error_pixels_mean": float(pixel_errors.mean()),
        "reprojection_error_pixels_max": float(pixel_errors.max()),
        "reprojection_error_meters_mean": float(court_errors.mean()),
        "reprojection_error_meters_max": float(court_errors.max()),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corners", type=Path, default=Path("data/reference_clip/court_corners_pixel.json"))
    parser.add_argument("--output", type=Path, default=Path("data/reference_clip/homography.json"))
    parser.add_argument("--frame", type=Path)
    parser.add_argument("--clip-id")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = compute_and_write_homography(
        args.corners,
        args.output,
        frame_path=args.frame,
        clip_id=args.clip_id,
    )
    print(f"Homography written to {args.output}")
    print(f"mean_px={payload['reprojection_error_pixels_mean']:.6f}")
    print(f"max_px={payload['reprojection_error_pixels_max']:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
