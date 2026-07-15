"""Explainable Stage 3 smoothing for legacy CFR and canonical VFR detections."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from src.project.clip_manifest import ClipManifest
from src.tracker.render_trajectory_overlay import render_trajectory_overlay
from src.tracker.trajectory_io import read_wasb_detections, write_smoothed_trajectory
from src.video.frame_timestamps import (
    FrameTimestampSidecar,
    timestamp_values,
    validate_sidecar_against_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_DIAGONAL_PX = math.hypot(1920, 1080)


@dataclass(frozen=True)
class SmoothingParams:
    """Thresholds shared by Madrid plus optional real-time VFR limits."""

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
    max_speed_px_s: float | None = None
    max_gap_seconds: float | None = None
    local_window_seconds: float | None = None
    smoothing_window_seconds: float | None = None
    normalized_speed_per_diagonal_s: float | None = None


def _has_timestamps(rows: list[dict]) -> bool:
    return bool(rows) and all(row.get("timestamp_seconds") is not None for row in rows)


def _canonical_diagonal(rows: list[dict]) -> float | None:
    for row in rows:
        width = row.get("canonical_width")
        height = row.get("canonical_height")
        if width is not None and height is not None:
            return math.hypot(float(width), float(height))
    return None


def _spatial_scale(rows: list[dict]) -> float:
    diagonal = _canonical_diagonal(rows)
    return diagonal / REFERENCE_DIAGONAL_PX if diagonal else 1.0


def _time_delta(rows: list[dict], start: int, end: int) -> float:
    if _has_timestamps(rows):
        return float(rows[end]["timestamp_seconds"] - rows[start]["timestamp_seconds"])
    return float(end - start)


def _effective_max_speed(rows: list[dict], params: SmoothingParams) -> float:
    if not _has_timestamps(rows):
        return params.max_jump_px
    if params.max_speed_px_s is not None:
        return params.max_speed_px_s
    diagonal = _canonical_diagonal(rows)
    if diagonal is not None and params.normalized_speed_per_diagonal_s is not None:
        return diagonal * params.normalized_speed_per_diagonal_s
    intervals = [
        float(current["timestamp_seconds"] - previous["timestamp_seconds"])
        for previous, current in zip(rows, rows[1:])
    ]
    median_interval = float(np.median(intervals)) if intervals else 1.0
    return params.max_jump_px / median_interval


def _distance(a: dict, b: dict, *, prefix: str = "smooth") -> float:
    return math.hypot(
        float(a[f"x_{prefix}"]) - float(b[f"x_{prefix}"]),
        float(a[f"y_{prefix}"]) - float(b[f"y_{prefix}"]),
    )


def _nearest_candidate(
    rows: list[dict],
    index: int,
    direction: int,
    max_steps: int,
    max_seconds: float | None = None,
) -> int | None:
    end = -1 if direction < 0 else len(rows)
    current = index + direction
    steps = 0
    while current != end and steps < max_steps:
        if max_seconds is not None and _has_timestamps(rows):
            if abs(float(rows[current]["timestamp_seconds"] - rows[index]["timestamp_seconds"])) > max_seconds:
                return None
        if rows[current]["source"] == "detected":
            return current
        current += direction
        steps += 1
    return None


def _temporal_alpha(rows: list[dict], start: int, current: int, end: int) -> float:
    span = _time_delta(rows, start, end)
    if span <= 0:
        raise ValueError("Trajectory time/frame span must be positive")
    return _time_delta(rows, start, current) / span


def _mark_rejected(row: dict, reason: str) -> None:
    row["source"] = "rejected"
    row["is_outlier"] = True
    row["reason"] = reason if not row["reason"] else f"{row['reason']}|{reason}"
    row["x_smooth"] = None
    row["y_smooth"] = None


def initialize_rows(raw_rows: list[dict], params: SmoothingParams) -> list[dict]:
    """Classify raw detections while preserving timing and canonical metadata."""
    rows = []
    for raw in raw_rows:
        confidence = float(raw["confidence"])
        has_xy = raw.get("x_raw") is not None and raw.get("y_raw") is not None
        detected_raw = bool(raw.get("detected_raw", has_xy))
        is_candidate = detected_raw and has_xy and confidence >= params.threshold_min
        if is_candidate:
            reason = ""
        elif not detected_raw:
            reason = "stage2_not_detected"
        elif not has_xy:
            reason = "missing_coordinates"
        else:
            reason = "low_confidence"
        rows.append(
            {
                "frame_id": int(raw["frame_id"]),
                "timestamp_seconds": raw.get("timestamp_seconds"),
                "x_raw": raw.get("x_raw"),
                "y_raw": raw.get("y_raw"),
                "confidence": confidence,
                "detected_raw": detected_raw,
                "x_smooth": raw.get("x_raw") if is_candidate else None,
                "y_smooth": raw.get("y_raw") if is_candidate else None,
                "source": "detected" if is_candidate else "missing",
                "is_outlier": False,
                "reason": reason,
                "canonical_width": raw.get("canonical_width"),
                "canonical_height": raw.get("canonical_height"),
            }
        )
    return rows


def reject_outliers(rows: list[dict], params: SmoothingParams) -> int:
    """Reject isolated spikes and jumps using px/s for VFR or px/frame for legacy data."""
    rejected = 0
    max_rate = _effective_max_speed(rows, params)
    scale = _spatial_scale(rows)

    for index, row in enumerate(rows):
        if row["source"] != "detected":
            continue

        prev_index = _nearest_candidate(
            rows, index, -1, params.local_window, params.local_window_seconds
        )
        next_index = _nearest_candidate(
            rows, index, 1, params.local_window, params.local_window_seconds
        )
        if prev_index is not None and next_index is not None:
            prev_row = rows[prev_index]
            next_row = rows[next_index]
            alpha = _temporal_alpha(rows, prev_index, index, next_index)
            expected_x = prev_row["x_smooth"] + alpha * (
                next_row["x_smooth"] - prev_row["x_smooth"]
            )
            expected_y = prev_row["y_smooth"] + alpha * (
                next_row["y_smooth"] - prev_row["y_smooth"]
            )
            deviation = math.hypot(row["x_smooth"] - expected_x, row["y_smooth"] - expected_y)
            bridge_rate = _distance(prev_row, next_row) / _time_delta(
                rows, prev_index, next_index
            )
            prev_rate = _distance(prev_row, row) / _time_delta(rows, prev_index, index)
            next_rate = _distance(row, next_row) / _time_delta(rows, index, next_index)
            bridge_is_plausible = bridge_rate <= max_rate
            spike_is_large = prev_rate > max_rate and next_rate > max_rate
            if (
                bridge_is_plausible
                and spike_is_large
                and deviation > params.isolated_outlier_px * scale
            ):
                _mark_rejected(row, "isolated_spike")
                rejected += 1
                continue

        prev_index = _nearest_candidate(
            rows,
            index,
            -1,
            params.max_gap_frames + 1,
            params.max_gap_seconds,
        )
        if prev_index is not None:
            prev_row = rows[prev_index]
            rate = _distance(prev_row, row) / _time_delta(rows, prev_index, index)
            if rate > max_rate:
                next_index = _nearest_candidate(
                    rows,
                    index,
                    1,
                    params.max_gap_frames + 1,
                    params.max_gap_seconds,
                )
                if next_index is None:
                    _mark_rejected(row, "impossible_jump")
                    rejected += 1
                else:
                    next_row = rows[next_index]
                    bridge_rate = _distance(prev_row, next_row) / _time_delta(
                        rows, prev_index, next_index
                    )
                    next_rate = _distance(row, next_row) / _time_delta(
                        rows, index, next_index
                    )
                    if bridge_rate <= max_rate and next_rate > max_rate:
                        _mark_rejected(row, "impossible_jump")
                        rejected += 1
    return rejected


def reject_local_prediction_breaks(rows: list[dict], params: SmoothingParams) -> int:
    """Reject points that break an otherwise coherent time-aware local bridge."""
    rejected = 0
    max_bridge_rate = _effective_max_speed(rows, params) * 0.5
    scale = _spatial_scale(rows)

    for index, row in enumerate(rows):
        if row["source"] != "detected":
            continue
        prev_index = _nearest_candidate(
            rows, index, -1, params.local_window, params.local_window_seconds
        )
        next_index = _nearest_candidate(
            rows, index, 1, params.local_window, params.local_window_seconds
        )
        if prev_index is None or next_index is None:
            continue
        prev_row = rows[prev_index]
        next_row = rows[next_index]
        alpha = _temporal_alpha(rows, prev_index, index, next_index)
        expected_x = prev_row["x_smooth"] + alpha * (
            next_row["x_smooth"] - prev_row["x_smooth"]
        )
        expected_y = prev_row["y_smooth"] + alpha * (
            next_row["y_smooth"] - prev_row["y_smooth"]
        )
        deviation = math.hypot(row["x_smooth"] - expected_x, row["y_smooth"] - expected_y)
        bridge_rate = _distance(prev_row, next_row) / _time_delta(
            rows, prev_index, next_index
        )
        prev_distance = _distance(prev_row, row)
        next_distance = _distance(row, next_row)
        bridge_is_coherent = bridge_rate <= max_bridge_rate
        point_breaks_bridge = (
            deviation >= params.residual_prediction_px * scale
            and prev_distance >= params.residual_neighbor_jump_px * scale
            and next_distance >= params.residual_neighbor_jump_px * scale
        )
        low_confidence_break = (
            row["confidence"] <= params.low_confidence_break_max_conf
            and deviation >= params.low_confidence_prediction_px * scale
            and prev_distance >= params.low_confidence_neighbor_jump_px * scale
            and next_distance >= params.low_confidence_neighbor_jump_px * scale
        )
        if bridge_is_coherent and (point_breaks_bridge or low_confidence_break):
            reason = (
                "low_confidence_prediction_break"
                if low_confidence_break
                else "local_prediction_break"
            )
            _mark_rejected(row, reason)
            rejected += 1
    return rejected


def interpolate_short_gaps(rows: list[dict], params: SmoothingParams) -> list[dict]:
    """Fill only gaps that satisfy both frame-count and real-duration limits."""
    detected_indices = [index for index, row in enumerate(rows) if row["source"] == "detected"]
    interpolated_gaps: list[dict] = []
    for start, end in zip(detected_indices, detected_indices[1:]):
        gap_frames = end - start - 1
        if gap_frames <= 0 or gap_frames > params.max_gap_frames:
            continue
        gap_seconds = _time_delta(rows, start, end) if _has_timestamps(rows) else None
        if (
            gap_seconds is not None
            and params.max_gap_seconds is not None
            and gap_seconds > params.max_gap_seconds
        ):
            continue
        start_row = rows[start]
        end_row = rows[end]
        interpolated_gaps.append(
            {
                "start_frame": start + 1,
                "end_frame": end - 1,
                "frames": gap_frames,
                "seconds": gap_seconds,
            }
        )
        for index in range(start + 1, end):
            alpha = _temporal_alpha(rows, start, index, end)
            rows[index]["x_smooth"] = start_row["x_smooth"] + alpha * (
                end_row["x_smooth"] - start_row["x_smooth"]
            )
            rows[index]["y_smooth"] = start_row["y_smooth"] + alpha * (
                end_row["y_smooth"] - start_row["y_smooth"]
            )
            if rows[index]["source"] == "missing":
                rows[index]["source"] = "interpolated"
                rows[index]["reason"] = "short_gap_interpolated"
            elif rows[index]["source"] == "rejected":
                rows[index]["reason"] = f"{rows[index]['reason']}|filled_by_interpolation"
    return interpolated_gaps


def _valid_segments(rows: list[dict]) -> list[list[int]]:
    segments: list[list[int]] = []
    current: list[int] = []
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
    """Apply centered smoothing inside valid spans, using time windows for VFR data."""
    if params.smoothing_window <= 1 and params.smoothing_window_seconds is None:
        return
    radius = params.smoothing_window // 2
    timed = _has_timestamps(rows) and params.smoothing_window_seconds is not None
    for segment in _valid_segments(rows):
        if len(segment) < 3:
            continue
        original = [(rows[index]["x_smooth"], rows[index]["y_smooth"]) for index in segment]
        for local_index, row_index in enumerate(segment):
            if timed:
                center = float(rows[row_index]["timestamp_seconds"])
                half_window = float(params.smoothing_window_seconds) / 2
                selected = [
                    point
                    for candidate_index, point in zip(segment, original)
                    if abs(float(rows[candidate_index]["timestamp_seconds"]) - center)
                    <= half_window
                ]
            else:
                start = max(0, local_index - radius)
                end = min(len(segment), local_index + radius + 1)
                selected = original[start:end]
            rows[row_index]["x_smooth"] = float(np.mean([point[0] for point in selected]))
            rows[row_index]["y_smooth"] = float(np.mean([point[1] for point in selected]))


def _maximum_rate(rows: list[dict], *, prefix: str, predicate) -> float:
    candidates = [
        (index, row)
        for index, row in enumerate(rows)
        if predicate(row) and row.get(f"x_{prefix}") is not None and row.get(f"y_{prefix}") is not None
    ]
    maximum = 0.0
    for (previous_index, previous), (current_index, current) in zip(candidates, candidates[1:]):
        delta = _time_delta(rows, previous_index, current_index)
        maximum = max(maximum, _distance(previous, current, prefix=prefix) / delta)
    return maximum


def _missing_gap_metrics(rows: list[dict]) -> tuple[int, float]:
    longest_frames = 0
    longest_seconds = 0.0
    start: int | None = None
    for index in range(len(rows) + 1):
        missing = index < len(rows) and rows[index]["x_smooth"] is None
        if missing and start is None:
            start = index
        elif not missing and start is not None:
            end = index - 1
            longest_frames = max(longest_frames, end - start + 1)
            if _has_timestamps(rows) and end > start:
                longest_seconds = max(
                    longest_seconds,
                    float(rows[end]["timestamp_seconds"] - rows[start]["timestamp_seconds"]),
                )
            start = None
    return longest_frames, longest_seconds


def build_quality_report(
    rows: list[dict],
    params: SmoothingParams,
    rejected_jumps: int,
    residual_rejections: int,
    interpolated_gaps: list[dict],
) -> dict:
    counts = Counter(row["source"] for row in rows)
    frames_total = len(rows)
    covered = sum(row["x_smooth"] is not None and row["y_smooth"] is not None for row in rows)
    rejected_frames = [row["frame_id"] for row in rows if row["source"] == "rejected"]
    reasons = Counter(
        reason
        for row in rows
        if row["source"] == "rejected"
        for reason in row["reason"].split("|")
        if reason and reason != "filled_by_interpolation"
    )
    max_missing_frames, max_missing_seconds = _missing_gap_metrics(rows)
    timed = _has_timestamps(rows)
    warnings = []
    if counts["missing"]:
        warnings.append("Some frames remain missing because gaps exceed the configured limits or are unbounded.")
    if counts["rejected"]:
        warnings.append("Rejected raw points require human review even when short gaps receive interpolated coordinates.")
    return {
        "status": "IMPLEMENTED_PENDING_HUMAN_VISUAL_GATE",
        "params": asdict(params),
        "timestamps_present": timed,
        "canonical_diagonal_px": _canonical_diagonal(rows),
        "spatial_threshold_scale": _spatial_scale(rows),
        "effective_max_speed_px_s": _effective_max_speed(rows, params) if timed else None,
        "frames_total": frames_total,
        "raw_detected_frames": sum(bool(row["detected_raw"]) for row in rows),
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
        "interpolated_gaps": interpolated_gaps,
        "max_gap_interpolated": max(
            (gap["frames"] for gap in interpolated_gaps), default=0
        ),
        "max_gap_interpolated_seconds": max(
            (gap["seconds"] or 0.0 for gap in interpolated_gaps), default=0.0
        ),
        "max_missing_gap_frames": max_missing_frames,
        "max_missing_gap_seconds": max_missing_seconds,
        "max_raw_speed_px_s" if timed else "max_raw_jump_px_per_frame": _maximum_rate(
            rows, prefix="raw", predicate=lambda row: row["detected_raw"]
        ),
        "max_smooth_speed_px_s" if timed else "max_smooth_jump_px_per_frame": _maximum_rate(
            rows,
            prefix="smooth",
            predicate=lambda row: row["x_smooth"] is not None,
        ),
        "rejected_frames": rejected_frames,
        "rejection_reasons": dict(sorted(reasons.items())),
        "warnings": warnings,
    }


def smooth_trajectory(
    raw_rows: list[dict], params: SmoothingParams | None = None
) -> tuple[list[dict], dict]:
    params = params or SmoothingParams()
    rows = initialize_rows(raw_rows, params)
    rejected_jumps = reject_outliers(rows, params)
    residual_rejections = reject_local_prediction_breaks(rows, params)
    interpolated_gaps = interpolate_short_gaps(rows, params)
    smooth_segments(rows, params)
    report = build_quality_report(
        rows, params, rejected_jumps, residual_rejections, interpolated_gaps
    )
    return rows, report


def run_stage_3(
    detections_csv: Path,
    video_path: Path,
    output_csv: Path,
    report_json: Path,
    overlay_mp4: Path,
    debug_overlay_mp4: Path,
    params: SmoothingParams,
    *,
    manifest_path: Path | None = None,
    frame_timestamps_path: Path | None = None,
    contact_sheet_path: Path | None = None,
) -> dict:
    """Execute legacy Stage 3 or canonical VFR Stage 3 with explicit clip inputs."""
    raw_rows = read_wasb_detections(detections_csv)
    manifest = ClipManifest.read(manifest_path) if manifest_path else None
    timestamps: list[float] | None = None
    if frame_timestamps_path:
        if manifest is None:
            raise ValueError("--frame-timestamps requires --manifest")
        sidecar = FrameTimestampSidecar.read(frame_timestamps_path)
        validate_sidecar_against_manifest(sidecar, manifest)
        timestamps = timestamp_values(sidecar.frames)
        if len(raw_rows) != len(timestamps):
            raise ValueError("Detection count does not match frame timestamp sidecar")
        for row, timestamp in zip(raw_rows, timestamps):
            if row["timestamp_seconds"] is None:
                row["timestamp_seconds"] = timestamp
            elif not math.isclose(row["timestamp_seconds"], timestamp, abs_tol=5e-10):
                raise ValueError("Detection timestamps do not match frame timestamp sidecar")
    if manifest:
        if len(raw_rows) != manifest.frames_total:
            raise ValueError("Detection count does not match manifest frames_total")
        for row in raw_rows:
            dimensions = (row["canonical_width"], row["canonical_height"])
            expected = (manifest.canonical_width, manifest.canonical_height)
            if dimensions != expected:
                raise ValueError("Detection canonical dimensions do not match manifest")

    rows, report = smooth_trajectory(raw_rows, params)
    report.update(
        {
            "clip_id": manifest.clip_id if manifest else "legacy_reference_clip",
            "manifest": str(manifest_path) if manifest_path else None,
            "frame_timestamps": str(frame_timestamps_path) if frame_timestamps_path else None,
            "stage_4_executed": False,
            "stage_5_executed": False,
        }
    )
    write_smoothed_trajectory(output_csv, rows)
    normal_metadata = render_trajectory_overlay(
        video_path,
        rows,
        overlay_mp4,
        debug=False,
        manifest=manifest,
        timestamps=timestamps,
    )
    debug_metadata = render_trajectory_overlay(
        video_path,
        rows,
        debug_overlay_mp4,
        debug=True,
        manifest=manifest,
        timestamps=timestamps,
    )
    report["outputs"] = {
        "csv": str(output_csv),
        "overlay": str(overlay_mp4),
        "debug_overlay": str(debug_overlay_mp4),
        "overlay_metadata": normal_metadata,
        "debug_overlay_metadata": debug_metadata,
    }
    if contact_sheet_path:
        if manifest is None or timestamps is None:
            raise ValueError("--contact-sheet requires canonical manifest and timestamps")
        from src.tracker.trajectory_review import generate_stage3_contact_sheet

        report["contact_sheet"] = generate_stage3_contact_sheet(
            video_path,
            manifest,
            timestamps,
            rows,
            contact_sheet_path,
        )
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smooth Stage 2 detections into a legacy or VFR-aware Stage 3 trajectory."
    )
    parser.add_argument(
        "--detections",
        type=Path,
        default=PROJECT_ROOT / "data" / "reference_clip" / "wasb_detections.csv",
    )
    parser.add_argument(
        "--video",
        type=Path,
        default=PROJECT_ROOT / "data" / "reference_clip" / "madrid_R1.mov",
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--frame-timestamps", type=Path)
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "stage_3" / "smoothed_trajectory.csv",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "stage_3" / "trajectory_quality_report.json",
    )
    parser.add_argument(
        "--overlay",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "stage_3" / "smoothed_trajectory_overlay.mp4",
    )
    parser.add_argument(
        "--debug-overlay",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "stage_3" / "trajectory_debug_overlay.mp4",
    )
    parser.add_argument("--contact-sheet", type=Path)
    parser.add_argument("--threshold-min", type=float, default=SmoothingParams.threshold_min)
    parser.add_argument("--max-gap-frames", type=int, default=SmoothingParams.max_gap_frames)
    parser.add_argument("--max-jump-px", type=float, default=SmoothingParams.max_jump_px)
    parser.add_argument("--local-window", type=int, default=SmoothingParams.local_window)
    parser.add_argument(
        "--isolated-outlier-px", type=float, default=SmoothingParams.isolated_outlier_px
    )
    parser.add_argument(
        "--residual-prediction-px",
        type=float,
        default=SmoothingParams.residual_prediction_px,
    )
    parser.add_argument(
        "--residual-neighbor-jump-px",
        type=float,
        default=SmoothingParams.residual_neighbor_jump_px,
    )
    parser.add_argument(
        "--low-confidence-break-max-conf",
        type=float,
        default=SmoothingParams.low_confidence_break_max_conf,
    )
    parser.add_argument(
        "--low-confidence-prediction-px",
        type=float,
        default=SmoothingParams.low_confidence_prediction_px,
    )
    parser.add_argument(
        "--low-confidence-neighbor-jump-px",
        type=float,
        default=SmoothingParams.low_confidence_neighbor_jump_px,
    )
    parser.add_argument(
        "--smoothing-window", type=int, default=SmoothingParams.smoothing_window
    )
    parser.add_argument("--max-speed-px-s", type=float)
    parser.add_argument("--max-gap-seconds", type=float)
    parser.add_argument("--local-window-seconds", type=float)
    parser.add_argument("--smoothing-window-seconds", type=float)
    parser.add_argument("--normalized-speed-per-diagonal-s", type=float)
    return parser.parse_args(argv)


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
        max_speed_px_s=args.max_speed_px_s,
        max_gap_seconds=args.max_gap_seconds,
        local_window_seconds=args.local_window_seconds,
        smoothing_window_seconds=args.smoothing_window_seconds,
        normalized_speed_per_diagonal_s=args.normalized_speed_per_diagonal_s,
    )
    report = run_stage_3(
        detections_csv=args.detections,
        video_path=args.video,
        output_csv=args.output_csv,
        report_json=args.report_json,
        overlay_mp4=args.overlay,
        debug_overlay_mp4=args.debug_overlay,
        params=params,
        manifest_path=args.manifest,
        frame_timestamps_path=args.frame_timestamps,
        contact_sheet_path=args.contact_sheet,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
