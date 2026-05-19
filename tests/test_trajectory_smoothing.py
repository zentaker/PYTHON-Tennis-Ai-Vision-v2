import csv

from src.tracker.trajectory_io import SMOOTHED_COLUMNS, write_smoothed_trajectory
from src.tracker.trajectory_smoothing import SmoothingParams, smooth_trajectory


def row(frame_id, x, y, confidence=0.9):
    return {"frame_id": frame_id, "x_raw": x, "y_raw": y, "confidence": confidence}


def test_short_gap_is_interpolated():
    rows, report = smooth_trajectory(
        [
            row(0, 0.0, 0.0),
            row(1, 100.0, 100.0, confidence=0.1),
            row(2, 200.0, 200.0, confidence=0.1),
            row(3, 30.0, 0.0),
        ],
        SmoothingParams(max_gap_frames=10, smoothing_window=1),
    )

    assert rows[1]["source"] == "interpolated"
    assert rows[2]["source"] == "interpolated"
    assert rows[1]["x_smooth"] == 10.0
    assert rows[2]["x_smooth"] == 20.0
    assert report["gaps_interpolated"] == 1
    assert report["max_gap_interpolated"] == 2


def test_long_gap_remains_missing():
    raw_rows = [row(0, 0.0, 0.0)]
    raw_rows.extend(row(i, 100.0, 100.0, confidence=0.1) for i in range(1, 12))
    raw_rows.append(row(12, 120.0, 0.0))

    rows, report = smooth_trajectory(raw_rows, SmoothingParams(max_gap_frames=10, smoothing_window=1))

    assert all(rows[i]["source"] == "missing" for i in range(1, 12))
    assert report["gaps_interpolated"] == 0
    assert report["frames_missing"] == 11


def test_isolated_outlier_between_coherent_points_is_rejected():
    rows, report = smooth_trajectory(
        [
            row(0, 0.0, 0.0),
            row(1, 10.0, 0.0),
            row(2, 500.0, 300.0),
            row(3, 30.0, 0.0),
            row(4, 40.0, 0.0),
        ],
        SmoothingParams(max_jump_px=120.0, isolated_outlier_px=80.0, smoothing_window=1),
    )

    assert rows[2]["source"] == "rejected"
    assert rows[2]["is_outlier"] is True
    assert "isolated_spike" in rows[2]["reason"]
    assert rows[2]["x_smooth"] == 20.0
    assert report["frames_rejected"] == 1


def test_long_segment_outlier_is_rejected_by_local_prediction_break():
    rows, report = smooth_trajectory(
        [
            row(0, 0.0, 0.0),
            row(1, 10.0, 0.0),
            row(2, 20.0, 150.0),
            row(3, 30.0, 0.0),
            row(4, 40.0, 0.0),
        ],
        SmoothingParams(
            max_jump_px=220.0,
            isolated_outlier_px=220.0,
            residual_prediction_px=100.0,
            residual_neighbor_jump_px=120.0,
            smoothing_window=1,
        ),
    )

    assert rows[2]["source"] == "rejected"
    assert "local_prediction_break" in rows[2]["reason"]
    assert rows[2]["x_smooth"] == 20.0
    assert rows[2]["y_smooth"] == 0.0
    assert report["residual_anomalies_rejected"] == 1


def test_high_speed_but_coherent_motion_is_not_rejected():
    rows, report = smooth_trajectory(
        [
            row(0, 0.0, 0.0),
            row(1, 100.0, 0.0),
            row(2, 200.0, 0.0),
            row(3, 300.0, 0.0),
            row(4, 400.0, 0.0),
        ],
        SmoothingParams(
            max_jump_px=120.0,
            residual_prediction_px=80.0,
            residual_neighbor_jump_px=90.0,
            smoothing_window=1,
        ),
    )

    assert [item["source"] for item in rows] == ["detected"] * 5
    assert report["frames_rejected"] == 0


def test_prediction_break_between_neighbors_is_interpolated():
    rows, _ = smooth_trajectory(
        [
            row(0, 0.0, 0.0),
            row(1, 10.0, 0.0),
            row(2, 20.0, 160.0),
            row(3, 30.0, 0.0),
        ],
        SmoothingParams(
            isolated_outlier_px=220.0,
            residual_prediction_px=100.0,
            residual_neighbor_jump_px=120.0,
            smoothing_window=1,
        ),
    )

    assert rows[2]["source"] == "rejected"
    assert rows[2]["y_smooth"] == 0.0
    assert rows[2]["reason"].endswith("filled_by_interpolation")


def test_trajectory_without_outliers_is_preserved():
    rows, report = smooth_trajectory(
        [row(i, float(i * 10), 5.0) for i in range(5)],
        SmoothingParams(max_jump_px=120.0, smoothing_window=1),
    )

    assert [item["source"] for item in rows] == ["detected"] * 5
    assert [item["x_smooth"] for item in rows] == [0.0, 10.0, 20.0, 30.0, 40.0]
    assert report["frames_rejected"] == 0
    assert report["frames_missing"] == 0


def test_second_pass_does_not_remove_clean_trajectory():
    rows, report = smooth_trajectory(
        [row(i, float(i * 30), float(i * 8)) for i in range(8)],
        SmoothingParams(
            max_jump_px=80.0,
            residual_prediction_px=20.0,
            residual_neighbor_jump_px=20.0,
            smoothing_window=1,
        ),
    )

    assert [item["source"] for item in rows] == ["detected"] * 8
    assert report["residual_anomalies_rejected"] == 0


def test_smoothed_csv_contains_expected_columns(tmp_path):
    rows, _ = smooth_trajectory(
        [row(0, 0.0, 0.0), row(1, 10.0, 0.0)],
        SmoothingParams(smoothing_window=1),
    )
    output_path = tmp_path / "smoothed.csv"

    write_smoothed_trajectory(output_path, rows)

    with output_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == SMOOTHED_COLUMNS
        assert len(list(reader)) == 2
