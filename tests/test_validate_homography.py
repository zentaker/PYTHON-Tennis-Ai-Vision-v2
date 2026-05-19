from __future__ import annotations

import json
from pathlib import Path

from src.court.coordinates import calibration_court_points
from src.court.homography import compute_homography
from src.court.validate_homography import validate_homography_payload, write_validation_report


def homography_payload() -> dict[str, object]:
    corners_court = dict(calibration_court_points("doubles"))
    corners_pixel = {
        name: (x * 55.0 + 900.0, y * -35.0 + 550.0)
        for name, (x, y) in corners_court.items()
    }
    h = compute_homography(corners_pixel, corners_court)
    return {
        "H_pixel_to_court": h.tolist(),
        "court_corners_pixel": {name: list(value) for name, value in corners_pixel.items()},
        "court_corners_court_meters": {name: list(value) for name, value in corners_court.items()},
        "court_mode": "doubles",
        "method": "cv2.findHomography(method=0)",
    }


def test_validate_homography_payload_reports_low_error() -> None:
    report = validate_homography_payload(homography_payload())

    assert report["court_to_pixel_error_pixels_mean"] < 1e-4
    assert report["pixel_to_court_error_meters_mean"] < 1e-5
    assert report["dod"]["passed"] is True  # type: ignore[index]


def test_write_validation_report_persists_json(tmp_path: Path) -> None:
    homography_path = tmp_path / "homography.json"
    output_path = tmp_path / "report.json"
    homography_path.write_text(json.dumps(homography_payload()), encoding="utf-8")

    report = write_validation_report(homography_path, output_path)

    assert output_path.exists()
    assert report["court_mode"] == "doubles"
