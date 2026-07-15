from __future__ import annotations

import csv
from collections import deque
from pathlib import Path

import numpy as np
import pytest

from src.tracker.render_trajectory_overlay import draw_trajectory_frame
from src.tracker.trajectory_io import read_wasb_detections
from src.tracker.trajectory_smoothing import SmoothingParams, parse_args, smooth_trajectory


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _a2_row(
    frame_id: int,
    timestamp: float,
    x: float,
    *,
    confidence: float = 0.9,
    detected: bool = True,
) -> dict:
    return {
        "frame_id": frame_id,
        "timestamp_seconds": timestamp,
        "x_pixel": x,
        "y_pixel": 100.0,
        "confidence": confidence,
        "detected": str(detected).lower(),
        "canonical_width": 2746,
        "canonical_height": 1536,
    }


def test_read_a2_csv_preserves_timestamps_detection_and_bounds(tmp_path: Path) -> None:
    path = tmp_path / "a2.csv"
    fields = list(_a2_row(0, 0.0, 10.0))
    _write_csv(
        path,
        [_a2_row(0, 0.0, 10.0), _a2_row(1, 1 / 60, 20.0, detected=False)],
        fields,
    )

    rows = read_wasb_detections(path)

    assert rows[0]["timestamp_seconds"] == 0.0
    assert rows[1]["detected_raw"] is False
    assert (rows[0]["canonical_width"], rows[0]["canonical_height"]) == (2746, 1536)


def test_read_legacy_csv_remains_compatible(tmp_path: Path) -> None:
    path = tmp_path / "legacy.csv"
    _write_csv(
        path,
        [{"frame_id": 0, "x_pixel": 10, "y_pixel": 20, "confidence": 0.9}],
        ["frame_id", "x_pixel", "y_pixel", "confidence"],
    )

    rows = read_wasb_detections(path)

    assert rows[0]["timestamp_seconds"] is None
    assert rows[0]["detected_raw"] is True
    assert rows[0]["canonical_width"] is None


@pytest.mark.parametrize(
    "rows, message",
    [
        ([_a2_row(0, 0.0, 10.0), _a2_row(1, 0.0, 20.0)], "strictly increasing"),
        ([_a2_row(0, 0.0, 10.0), _a2_row(2, 0.02, 20.0)], "consecutive"),
        ([_a2_row(0, 0.0, 10.0), _a2_row(0, 0.02, 20.0)], "consecutive"),
    ],
)
def test_a2_csv_rejects_invalid_timeline_or_frame_ids(
    tmp_path: Path, rows: list[dict], message: str
) -> None:
    path = tmp_path / "invalid.csv"
    _write_csv(path, rows, list(rows[0]))

    with pytest.raises(ValueError, match=message):
        read_wasb_detections(path)


def test_a2_csv_rejects_detected_point_outside_canonical_bounds(tmp_path: Path) -> None:
    path = tmp_path / "outside.csv"
    row = _a2_row(0, 0.0, 2746.0)
    _write_csv(path, [row], list(row))

    with pytest.raises(ValueError, match="outside canonical bounds"):
        read_wasb_detections(path)


def test_vfr_interpolation_uses_time_ratio_not_frame_ratio() -> None:
    raw = [
        {**_a2_row(0, 0.0, 0.0), "x_raw": 0.0, "y_raw": 0.0, "detected_raw": True},
        {
            **_a2_row(1, 1 / 60, 50.0, confidence=0.1, detected=False),
            "x_raw": 50.0,
            "y_raw": 0.0,
            "detected_raw": False,
        },
        {**_a2_row(2, 1 / 20, 30.0), "x_raw": 30.0, "y_raw": 0.0, "detected_raw": True},
    ]
    for row in raw:
        row["timestamp_seconds"] = row.pop("timestamp_seconds")
        row["confidence"] = float(row["confidence"])
        row["canonical_width"] = 2746
        row["canonical_height"] = 1536

    rows, report = smooth_trajectory(
        raw,
        SmoothingParams(
            max_gap_frames=2,
            max_gap_seconds=0.06,
            smoothing_window=1,
            max_speed_px_s=5000,
        ),
    )

    assert rows[1]["source"] == "interpolated"
    assert rows[1]["x_smooth"] == pytest.approx(10.0)
    assert report["max_gap_interpolated_seconds"] == pytest.approx(0.05)


def test_vfr_gap_duration_can_block_frame_count_eligible_gap() -> None:
    raw = [
        {
            "frame_id": 0,
            "timestamp_seconds": 0.0,
            "x_raw": 0.0,
            "y_raw": 0.0,
            "confidence": 0.9,
            "detected_raw": True,
            "canonical_width": 2746,
            "canonical_height": 1536,
        },
        {
            "frame_id": 1,
            "timestamp_seconds": 1 / 60,
            "x_raw": 10.0,
            "y_raw": 0.0,
            "confidence": 0.1,
            "detected_raw": False,
            "canonical_width": 2746,
            "canonical_height": 1536,
        },
        {
            "frame_id": 2,
            "timestamp_seconds": 1 / 20,
            "x_raw": 30.0,
            "y_raw": 0.0,
            "confidence": 0.9,
            "detected_raw": True,
            "canonical_width": 2746,
            "canonical_height": 1536,
        },
    ]

    rows, report = smooth_trajectory(
        raw,
        SmoothingParams(max_gap_frames=2, max_gap_seconds=0.04, smoothing_window=1),
    )

    assert rows[1]["source"] == "missing"
    assert report["gaps_interpolated"] == 0


def test_vfr_speed_px_s_rejects_isolated_spike() -> None:
    raw = [
        {
            "frame_id": index,
            "timestamp_seconds": index * 0.01,
            "x_raw": x,
            "y_raw": 0.0,
            "confidence": 0.9,
            "detected_raw": True,
            "canonical_width": 2746,
            "canonical_height": 1536,
        }
        for index, x in enumerate([0.0, 100.0, 2.0])
    ]

    rows, report = smooth_trajectory(
        raw,
        SmoothingParams(max_speed_px_s=1000, isolated_outlier_px=20, smoothing_window=1),
    )

    assert rows[1]["source"] == "rejected"
    assert report["max_raw_speed_px_s"] == pytest.approx(10000.0)


def test_draw_stage3_frame_keeps_a2_canonical_orientation() -> None:
    frame = np.zeros((1536, 2746, 3), dtype=np.uint8)
    row = {
        "frame_id": 0,
        "timestamp_seconds": 0.0,
        "x_raw": 100.0,
        "y_raw": 100.0,
        "x_smooth": 100.0,
        "y_smooth": 100.0,
        "confidence": 0.9,
        "source": "detected",
        "reason": "",
    }

    output = draw_trajectory_frame(frame, row, deque(maxlen=18), debug=True)

    assert output.shape == (1536, 2746, 3)


def test_stage3_cli_accepts_explicit_a2_paths() -> None:
    args = parse_args(
        [
            "--detections",
            "data/clips/nivel_a2_01/wasb_detections.csv",
            "--video",
            "data/clips/nivel_a2_01/source.mp4",
            "--manifest",
            "data/clips/nivel_a2_01/clip_manifest.json",
            "--frame-timestamps",
            "data/clips/nivel_a2_01/frame_timestamps.json",
            "--output-csv",
            "outputs/nivel_a2_01/stage_3/smoothed_trajectory.csv",
            "--report-json",
            "outputs/nivel_a2_01/stage_3/trajectory_quality_report.json",
            "--overlay",
            "outputs/nivel_a2_01/stage_3/smoothed_trajectory_overlay.mp4",
            "--debug-overlay",
            "outputs/nivel_a2_01/stage_3/trajectory_debug_overlay.mp4",
        ]
    )

    assert args.manifest.name == "clip_manifest.json"
    assert args.frame_timestamps.name == "frame_timestamps.json"
    assert args.overlay.name == "smoothed_trajectory_overlay.mp4"
