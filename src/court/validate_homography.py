"""Validate Stage 1 homography reprojection errors."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.court.coordinates import CALIBRATION_POINT_ORDER
from src.court.homography import apply_homography, ordered_points


def load_homography_payload(path: Path) -> dict[str, object]:
    """Load homography JSON payload."""
    return json.loads(path.read_text(encoding="utf-8"))


def validate_homography_payload(payload: dict[str, object]) -> dict[str, object]:
    """Measure pixel->court and court->pixel reprojection error."""
    homography = np.array(payload["H_pixel_to_court"], dtype=np.float64)
    inverse_h = np.linalg.inv(homography)
    corners_pixel = {
        name: tuple(payload["court_corners_pixel"][name])  # type: ignore[index]
        for name in CALIBRATION_POINT_ORDER
    }
    corners_court = {
        name: tuple(payload["court_corners_court_meters"][name])  # type: ignore[index]
        for name in CALIBRATION_POINT_ORDER
    }

    pixel_points = ordered_points(corners_pixel)
    court_points = ordered_points(corners_court)
    projected_court = apply_homography(homography, pixel_points)
    projected_pixels = apply_homography(inverse_h, court_points)

    errors_m = np.linalg.norm(projected_court - court_points, axis=1)
    errors_px = np.linalg.norm(projected_pixels - pixel_points, axis=1)

    per_point = []
    for index, name in enumerate(CALIBRATION_POINT_ORDER):
        per_point.append(
            {
                "point": name,
                "pixel_error": float(errors_px[index]),
                "court_error_meters": float(errors_m[index]),
            }
        )

    return {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "clip_id": payload.get("clip_id"),
        "court_mode": payload["court_mode"],
        "method": payload["method"],
        "frame_dimensions": payload.get("frame_dimensions"),
        "orientation_validation": payload.get("orientation_validation"),
        "pixel_to_court_error_meters_mean": float(errors_m.mean()),
        "pixel_to_court_error_meters_max": float(errors_m.max()),
        "court_to_pixel_error_pixels_mean": float(errors_px.mean()),
        "court_to_pixel_error_pixels_max": float(errors_px.max()),
        "per_point": per_point,
        "dod": {
            "mean_pixel_error_threshold": 5.0,
            "max_pixel_error_threshold": 15.0,
            "passed": bool(errors_px.mean() < 5.0 and errors_px.max() < 15.0),
        },
    }


def write_validation_report(homography_path: Path, output_path: Path) -> dict[str, object]:
    """Validate homography and persist a report JSON."""
    payload = load_homography_payload(homography_path)
    report = validate_homography_payload(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--homography", type=Path, default=Path("data/reference_clip/homography.json"))
    parser.add_argument("--output", type=Path, default=Path("outputs/stage_1/reprojection_error_report.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = write_validation_report(args.homography, args.output)
    print(f"Validation report written to {args.output}")
    print(f"mean_px={report['court_to_pixel_error_pixels_mean']:.6f}")
    print(f"max_px={report['court_to_pixel_error_pixels_max']:.6f}")
    print(f"mean_m={report['pixel_to_court_error_meters_mean']:.6f}")
    print(f"max_m={report['pixel_to_court_error_meters_max']:.6f}")
    return 0 if report["dod"]["passed"] else 1  # type: ignore[index]


if __name__ == "__main__":
    raise SystemExit(main())
