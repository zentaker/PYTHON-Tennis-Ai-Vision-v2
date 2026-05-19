"""Stage 3 trajectory smoothing for WASB detections."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from src.tracker.render_trajectory_overlay import render_trajectory_overlay
from src.tracker.trajectory_io import read_wasb_detections, write_smoothed_trajectory


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SmoothingParams:
    threshold_min: float = 0.5
    max_gap_frames: int = 10
    max_jump_px: float = 220.0
    local_window: int = 7
    isolated_outlier_px: float = 140.0
    residual_prediction_px: float = 120.0
    residual_neighbor_jump_px: float = 135.0
    low_confidence_break_max_conf: float = 0.6
    low_confidence_prediction_px: float = 55.0
    low_confidence_neighbor_jump_px: float = 50.0
    smoothing_window: int = 5


def _distance(a: dict, b: dict) -> float:
    return math.hypot(float(a["x_smooth"]) - float(b["x_smooth"]), float(a["y_smooth"]) - float(b["y_smooth"]))


def _nearest_candidate(rows: list[dict], index: int, direction: int, max_steps: int) -> int | None:
    end = -1 if direction < 0 else len(rows)
    current = index + direction
    steps = 0
    while current != end and steps < max_steps:
        if rows[current]["source"] == "detected":
            return current
        current += direction
        steps += 1
    return None


def _mark_rejected(row: dict, reason: str) -> None:
    row["source"] = "rejected"
    row["is_outlier"] = True
    row["reason"] = reason if not row["reason"] else f"{row['reason']}|{reason}"
    row["x_smooth"] = None
    row["y_smooth"] = None


def initialize_rows(raw_rows: list[dict], params: SmoothingParams) -> list[dict]:
    rows = []
    for raw in raw_rows:
        confidence = float(raw["confidence"])
        has_xy = raw.get("x_raw") is not None and raw.get("y_raw") is not None
        is_candidate = has_xy and confidence >= params.threshold_min
        rows.append(
            {
                "frame_id": int(raw["frame_id"]),
                "x_raw": raw.get("x_raw"),
                "y_raw": raw.get("y_raw"),
                "confidence": confidence,
                "x_smooth": raw.get("x_raw") if is_candidate else None,
                "y_smooth": raw.get("y_raw") if is_candidate else None,
                "source": "detected" if is_candidate else "missing",
                "is_outlier": False,
                "reason": "" if is_candidate else "low_confidence",
            }
        )
    return rows


def reject_outliers(rows: list[dict], params: SmoothingParams) -> int:
    """Reject isolated spikes and physically implausible jumps."""
    rejected = 0

    for index, row in enumerate(rows):
        if row["source"] != "detected":
            continue

        prev_index = _nearest_candidate(rows, index, -1, params.local_window)
        next_index = _nearest_candidate(rows, index, 1, params.local_window)

        if prev_index is not None and next_index is not None:
            prev_row = rows[prev_index]
            next_row = rows[next_index]
            span = next_index - prev_index
            if span > 0:
                alpha = (index - prev_index) / span
                expected_x = prev_row["x_smooth"] + alpha * (next_row["x_smooth"] - prev_row["x_smooth"])
                expected_y = prev_row["y_smooth"] + alpha * (next_row["y_smooth"] - prev_row["y_smooth"])
                deviation = math.hypot(row["x_smooth"] - expected_x, row["y_smooth"] - expected_y)
                bridge_speed = _distance(prev_row, next_row) / span
                local_limit = max(params.isolated_outlier_px, params.max_jump_px, bridge_speed * 3.0)
                prev_jump = _distance(prev_row, row) / max(index - prev_index, 1)
                next_jump = _distance(row, next_row) / max(next_index - index, 1)
                bridge_is_plausible = bridge_speed <= params.max_jump_px
                spike_is_large = prev_jump > params.max_jump_px and next_jump > params.max_jump_px
                if bridge_is_plausible and spike_is_large and deviation > local_limit:
                    _mark_rejected(row, "isolated_spike")
                    rejected += 1
                    continue

        prev_index = _nearest_candidate(rows, index, -1, params.max_gap_frames + 1)
        if prev_index is not None:
            prev_row = rows[prev_index]
            gap = index - prev_index
            speed = _distance(prev_row, row) / gap
            if speed > params.max_jump_px:
                next_index = _nearest_candidate(rows, index, 1, params.max_gap_frames + 1)
                if next_index is None:
                    _mark_rejected(row, "impossible_jump")
                    rejected += 1
                else:
                    next_row = rows[next_index]
                    bridge_speed = _distance(prev_row, next_row) / (next_index - prev_index)
                    next_speed = _distance(row, next_row) / (next_index - index)
                    if bridge_speed <= params.max_jump_px and next_speed > params.max_jump_px:
                        _mark_rejected(row, "impossible_jump")
                        rejected += 1

    return rejected


def reject_local_prediction_breaks(rows: list[dict], params: SmoothingParams) -> int:
    """Reject residual points that break an otherwise coherent local bridge."""
    rejected = 0
    max_bridge_speed = params.max_jump_px * 0.5

    for index, row in enumerate(rows):
        if row["source"] != "detected":
            continue

        prev_index = _nearest_candidate(rows, index, -1, params.local_window)
        next_index = _nearest_candidate(rows, index, 1, params.local_window)
        if prev_index is None or next_index is None:
            continue

        prev_row = rows[prev_index]
        next_row = rows[next_index]
        span = next_index - prev_index
        if span <= 0:
            continue

        alpha = (index - prev_index) / span
        expected_x = prev_row["x_smooth"] + alpha * (next_row["x_smooth"] - prev_row["x_smooth"])
        expected_y = prev_row["y_smooth"] + alpha * (next_row["y_smooth"] - prev_row["y_smooth"])
        deviation = math.hypot(row["x_smooth"] - expected_x, row["y_smooth"] - expected_y)
        bridge_speed = _distance(prev_row, next_row) / span
        prev_distance = _distance(prev_row, row)
        next_distance = _distance(row, next_row)

        bridge_is_coherent = bridge_speed <= max_bridge_speed
        point_breaks_bridge = (
            deviation >= params.residual_prediction_px
            and prev_distance >= params.residual_neighbor_jump_px
            and next_distance >= params.residual_neighbor_jump_px
        )
        low_confidence_break = (
            row["confidence"] <= params.low_confidence_break_max_conf
            and deviation >= params.low_confidence_prediction_px
            and prev_distance >= params.low_confidence_neighbor_jump_px
            and next_distance >= params.low_confidence_neighbor_jump_px
        )

        if bridge_is_coherent and (point_breaks_bridge or low_confidence_break):
            reason = "low_confidence_prediction_break" if low_confidence_break else "local_prediction_break"
            _mark_rejected(row, reason)
            rejected += 1

    return rejected


def interpolate_short_gaps(rows: list[dict], params: SmoothingParams) -> list[int]:
    """Linearly fill short gaps between accepted detected points."""
    detected_indices = [index for index, row in enumerate(rows) if row["source"] == "detected"]
    interpolated_gaps = []

    for start, end in zip(detected_indices, detected_indices[1:]):
        gap = end - start - 1
        if gap <= 0:
            continue
        if gap > params.max_gap_frames:
            continue

        start_row = rows[start]
        end_row = rows[end]
        interpolated_gaps.append(gap)
        for index in range(start + 1, end):
            alpha = (index - start) / (end - start)
            rows[index]["x_smooth"] = start_row["x_smooth"] + alpha * (end_row["x_smooth"] - start_row["x_smooth"])
            rows[index]["y_smooth"] = start_row["y_smooth"] + alpha * (end_row["y_smooth"] - start_row["y_smooth"])
            if rows[index]["source"] == "missing":
                rows[index]["source"] = "interpolated"
                rows[index]["reason"] = "short_gap_interpolated"
            elif rows[index]["source"] == "rejected":
                rows[index]["reason"] = f"{rows[index]['reason']}|filled_by_interpolation"

    return interpolated_gaps


def _valid_segments(rows: list[dict]) -> list[list[int]]:
    segments = []
    current = []
    for index, row in enumerate(rows):
        if row["x_smooth"] is not None and row["y_smooth"] is not None:
            current.append(index)
        elif current:
            segments.append(current)
            current = []
    if current:
        segments.append(current)
    return segments


def smooth_segments(rows: list[dict], params: SmoothingParams) -> None:
    """Apply a centered moving average within continuous valid spans."""
    if params.smoothing_window <= 1:
        return

    radius = params.smoothing_window // 2
    for segment in _valid_segments(rows):
        if len(segment) < 3:
            continue
        original = [(rows[index]["x_smooth"], rows[index]["y_smooth"]) for index in segment]
        for local_index, row_index in enumerate(segment):
            start = max(0, local_index - radius)
            end = min(len(segment), local_index + radius + 1)
            window = original[start:end]
            rows[row_index]["x_smooth"] = float(np.mean([point[0] for point in window]))
            rows[row_index]["y_smooth"] = float(np.mean([point[1] for point in window]))


def build_quality_report(
    rows: list[dict],
    params: SmoothingParams,
    rejected_jumps: int,
    residual_rejections: int,
    interpolated_gaps: list[int],
) -> dict:
    counts = {"detected": 0, "rejected": 0, "interpolated": 0, "missing": 0}
    for row in rows:
        counts[row["source"]] = counts.get(row["source"], 0) + 1

    frames_total = len(rows)
    covered = sum(1 for row in rows if row["x_smooth"] is not None and row["y_smooth"] is not None)
    warnings = []
    if counts["missing"]:
        warnings.append("Some frames remain missing because gaps were longer than max_gap_frames or outside detected spans.")
    if counts["rejected"]:
        warnings.append("Rejected frames may still have interpolated smoothed coordinates when bounded by short valid gaps.")

    return {
        "params": asdict(params),
        "frames_total": frames_total,
        "frames_detected": counts["detected"],
        "frames_rejected": counts["rejected"],
        "frames_interpolated": counts["interpolated"],
        "frames_missing": counts["missing"],
        "final_coverage_frames": covered,
        "final_coverage_rate": covered / frames_total if frames_total else 0.0,
        "jumps_rejected": rejected_jumps,
        "residual_anomalies_rejected": residual_rejections,
        "segments_anomalous_detected": residual_rejections,
        "gaps_interpolated": len(interpolated_gaps),
        "max_gap_interpolated": max(interpolated_gaps) if interpolated_gaps else 0,
        "warnings": warnings,
    }


def smooth_trajectory(raw_rows: list[dict], params: SmoothingParams | None = None) -> tuple[list[dict], dict]:
    params = params or SmoothingParams()
    rows = initialize_rows(raw_rows, params)
    rejected_jumps = reject_outliers(rows, params)
    residual_rejections = reject_local_prediction_breaks(rows, params)
    interpolated_gaps = interpolate_short_gaps(rows, params)
    smooth_segments(rows, params)
    report = build_quality_report(rows, params, rejected_jumps, residual_rejections, interpolated_gaps)
    return rows, report


def run_stage_3(
    detections_csv: Path,
    video_path: Path,
    output_csv: Path,
    report_json: Path,
    overlay_mp4: Path,
    debug_overlay_mp4: Path,
    params: SmoothingParams,
) -> dict:
    raw_rows = read_wasb_detections(detections_csv)
    rows, report = smooth_trajectory(raw_rows, params)
    write_smoothed_trajectory(output_csv, rows)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    render_trajectory_overlay(video_path, rows, overlay_mp4, debug=False)
    render_trajectory_overlay(video_path, rows, debug_overlay_mp4, debug=True)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smooth Stage 2 WASB detections into a Stage 3 trajectory.")
    parser.add_argument("--detections", type=Path, default=PROJECT_ROOT / "data" / "reference_clip" / "wasb_detections.csv")
    parser.add_argument("--video", type=Path, default=PROJECT_ROOT / "data" / "reference_clip" / "madrid_R1.mov")
    parser.add_argument("--output-csv", type=Path, default=PROJECT_ROOT / "outputs" / "stage_3" / "smoothed_trajectory.csv")
    parser.add_argument("--report-json", type=Path, default=PROJECT_ROOT / "outputs" / "stage_3" / "trajectory_quality_report.json")
    parser.add_argument("--overlay", type=Path, default=PROJECT_ROOT / "outputs" / "stage_3" / "smoothed_trajectory_overlay.mp4")
    parser.add_argument("--debug-overlay", type=Path, default=PROJECT_ROOT / "outputs" / "stage_3" / "trajectory_debug_overlay.mp4")
    parser.add_argument("--threshold-min", type=float, default=SmoothingParams.threshold_min)
    parser.add_argument("--max-gap-frames", type=int, default=SmoothingParams.max_gap_frames)
    parser.add_argument("--max-jump-px", type=float, default=SmoothingParams.max_jump_px)
    parser.add_argument("--local-window", type=int, default=SmoothingParams.local_window)
    parser.add_argument("--isolated-outlier-px", type=float, default=SmoothingParams.isolated_outlier_px)
    parser.add_argument("--residual-prediction-px", type=float, default=SmoothingParams.residual_prediction_px)
    parser.add_argument("--residual-neighbor-jump-px", type=float, default=SmoothingParams.residual_neighbor_jump_px)
    parser.add_argument("--low-confidence-break-max-conf", type=float, default=SmoothingParams.low_confidence_break_max_conf)
    parser.add_argument("--low-confidence-prediction-px", type=float, default=SmoothingParams.low_confidence_prediction_px)
    parser.add_argument("--low-confidence-neighbor-jump-px", type=float, default=SmoothingParams.low_confidence_neighbor_jump_px)
    parser.add_argument("--smoothing-window", type=int, default=SmoothingParams.smoothing_window)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    params = SmoothingParams(
        threshold_min=args.threshold_min,
        max_gap_frames=args.max_gap_frames,
        max_jump_px=args.max_jump_px,
        local_window=args.local_window,
        isolated_outlier_px=args.isolated_outlier_px,
        residual_prediction_px=args.residual_prediction_px,
        residual_neighbor_jump_px=args.residual_neighbor_jump_px,
        low_confidence_break_max_conf=args.low_confidence_break_max_conf,
        low_confidence_prediction_px=args.low_confidence_prediction_px,
        low_confidence_neighbor_jump_px=args.low_confidence_neighbor_jump_px,
        smoothing_window=args.smoothing_window,
    )
    report = run_stage_3(
        detections_csv=args.detections,
        video_path=args.video,
        output_csv=args.output_csv,
        report_json=args.report_json,
        overlay_mp4=args.overlay,
        debug_overlay_mp4=args.debug_overlay,
        params=params,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
