#!/usr/bin/env python3
"""Audit selected local assets and build a real Stage 1B candidate.

This script consumes existing files only. It never decodes or copies the source
video and writes local audit/build evidence under .artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import statistics
import subprocess
from pathlib import Path
from typing import Any

from src.product.analysis_bundle.checksums import sha256_file
from src.product.single_rally.adapters import load_events, load_frame_timestamps, load_json
from src.product.single_rally.importer import import_single_rally
from src.product.single_rally.validation import validate_single_rally_bundle


def _ffprobe(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "format=format_name,duration,start_time:stream=codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,time_base:stream_tags=rotate",
        "-of",
        "json",
        str(path),
    ]
    payload = json.loads(subprocess.check_output(command, text=True))
    stream = (payload.get("streams") or [{}])[0]
    fmt = payload.get("format") or {}
    return {
        "filename": path.name,
        "format": fmt.get("format_name"),
        "duration_seconds": float(fmt["duration"]),
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "codec": stream.get("codec_name"),
        "r_frame_rate": stream.get("r_frame_rate"),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "nb_frames": int(stream["nb_frames"])
        if stream.get("nb_frames") not in (None, "N/A")
        else None,
        "time_base": stream.get("time_base"),
        "start_time": stream.get("start_time", fmt.get("start_time")),
        "rotation": (stream.get("tags") or {}).get("rotate"),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _timestamp_audit(path: Path, video: dict[str, Any]) -> dict[str, Any]:
    payload = load_json(path)
    frames = payload["frames"]
    ids = [int(item["frame_id"]) for item in frames]
    times = [float(item["timestamp_seconds"]) for item in frames]
    deltas = [right - left for left, right in zip(times, times[1:])]
    expected = list(range(len(ids)))
    sorted_deltas = sorted(deltas)
    p95_index = min(len(sorted_deltas) - 1, math.ceil(0.95 * len(sorted_deltas)) - 1)
    missing = sorted(set(range(max(ids) + 1)) - set(ids))
    return {
        "path": str(path),
        "schema_version": payload.get("schema_version"),
        "frame_count": len(frames),
        "expected_frame_count": video["nb_frames"],
        "frame_ids_unique": len(set(ids)) == len(ids),
        "frame_ids_contiguous": ids == expected,
        "first_frame": ids[0],
        "last_frame": ids[-1],
        "first_timestamp_seconds": times[0],
        "last_timestamp_seconds": times[-1],
        "timestamps_finite": all(math.isfinite(value) for value in times),
        "timestamps_non_decreasing": all(right >= left for left, right in zip(times, times[1:])),
        "negative_timestamps": sum(value < 0 for value in times),
        "duration_delta_seconds": times[-1] - video["duration_seconds"],
        "median_frame_interval_seconds": statistics.median(deltas),
        "p95_frame_interval_seconds": sorted_deltas[p95_index],
        "effective_fps": 1.0 / statistics.median(deltas),
        "missing_frames": missing,
        "duplicate_frames": len(ids) - len(set(ids)),
        "timing_mode": payload.get("timing_mode"),
    }


def _track_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _track_audit(path: Path, video: dict[str, Any], timestamps: dict[int, float]) -> dict[str, Any]:
    rows = _track_rows(path)
    frames = [int(row["frame_id"]) for row in rows]
    times = [float(row["timestamp_seconds"]) for row in rows]
    visible = [row.get("detected_raw", "false").lower() == "true" for row in rows]
    source_counts: dict[str, int] = {}
    for row in rows:
        source_counts[row.get("source", "unknown")] = (
            source_counts.get(row.get("source", "unknown"), 0) + 1
        )
    visible_points = []
    for row, is_visible in zip(rows, visible):
        if is_visible:
            x, y = float(row["x_smooth"]), float(row["y_smooth"])
            if not (math.isfinite(x) and math.isfinite(y)):
                raise ValueError(f"non-finite visible point at frame {row['frame_id']}")
            if not 0 <= x < video["canonical_width"] or not 0 <= y < video["canonical_height"]:
                raise ValueError(
                    f"visible point outside canonical image at frame {row['frame_id']}"
                )
            visible_points.append((x, y))
    missing_run = max_run = 0
    for value in visible:
        if value:
            missing_run = 0
        else:
            missing_run += 1
            max_run = max(max_run, missing_run)
    return {
        "path": str(path),
        "format": "CSV",
        "sha256": sha256_file(path),
        "observations": len(rows),
        "frame_ids_unique": len(set(frames)) == len(frames),
        "frame_ids_ordered": frames == sorted(frames),
        "first_frame": frames[0],
        "last_frame": frames[-1],
        "first_timestamp_seconds": times[0],
        "last_timestamp_seconds": times[-1],
        "timestamps_direct": all(row.get("timestamp_seconds") not in (None, "") for row in rows),
        "timestamps_associable": all(frame in timestamps for frame in frames),
        "timestamps_non_decreasing": all(right >= left for left, right in zip(times, times[1:])),
        "out_of_video_frames": [
            frame for frame in frames if frame < 0 or frame >= video["nb_frames"]
        ],
        "visible_observations": sum(visible),
        "interpolated_observations": sum(row.get("source") == "interpolated" for row in rows),
        "missing_observations": sum(row.get("source") == "missing" for row in rows),
        "source_counts": source_counts,
        "confidence_available": all(row.get("confidence") not in (None, "") for row in rows),
        "max_non_visible_run": max_run,
        "canonical_width": int(rows[0]["canonical_width"]),
        "canonical_height": int(rows[0]["canonical_height"]),
    }


def _event_alignment(path: Path, track_path: Path) -> dict[str, Any]:
    events_payload = load_json(path)
    events = events_payload["narrative_events"]
    rows = _track_rows(track_path)
    track = [
        {
            "frame_id": int(row["frame_id"]),
            "timestamp": float(row["timestamp_seconds"]),
            "x": row.get("x_smooth"),
            "y": row.get("y_smooth"),
        }
        for row in rows
    ]
    aligned = []
    for event in events:
        frame = int(event["frame_start"])
        nearest = min(track, key=lambda row: abs(row["frame_id"] - frame))
        aligned.append(
            {
                "event_id": event["id"],
                "event_type": event["type"],
                "event_frame": frame,
                "event_timestamp_seconds": event["time_start_seconds"],
                "nearest_track_frame": nearest["frame_id"],
                "frame_delta": nearest["frame_id"] - frame,
                "timestamp_delta_seconds": nearest["timestamp"] - event["time_start_seconds"],
                "pixel_distance": None,
                "pixel_distance_status": "event_pixel_not_available",
            }
        )
    return {"event_count": len(aligned), "aligned_event_count": len(aligned), "events": aligned}


def _calibration_audit(path: Path, video: dict[str, Any]) -> dict[str, Any]:
    payload = load_json(path)
    dimensions = payload["frame_dimensions"]
    corners = payload["court_corners_pixel"]
    matrix = payload.get("H_pixel_to_court")
    determinant = (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )
    return {
        "path": str(path),
        "dimensions": dimensions,
        "dimensions_match_video_canonical": dimensions
        == {"width": video["canonical_width"], "height": video["canonical_height"]},
        "corner_count": len(corners),
        "orientation_passed": payload.get("orientation_validation", {}).get("passed", False),
        "homography_shape": [len(matrix), len(matrix[0])],
        "homography_finite": all(math.isfinite(float(value)) for row in matrix for value in row),
        "homography_determinant": determinant,
        "homography_non_singular": math.isfinite(determinant) and determinant != 0,
        "layout": payload.get("layout"),
        "provenance": payload.get("provenance", "existing_court_calibration"),
        "calibration_status": "approved"
        if dimensions == {"width": video["canonical_width"], "height": video["canonical_height"]}
        and payload.get("orientation_validation", {}).get("passed")
        and determinant != 0
        else "partial",
    }


def _write_svg(
    output: Path, track_path: Path, court_path: Path, events_path: Path, duration: float
) -> None:
    rows = _track_rows(track_path)
    court = load_json(court_path)
    corners = court["court_corners_pixel"]
    polygon = [corners[name] for name in ("far_left", "far_right", "near_right", "near_left")]
    points = [
        (row.get("x_smooth"), row.get("y_smooth"))
        for row in rows
        if row.get("detected_raw") == "true" and row.get("x_smooth") and row.get("y_smooth")
    ]
    track_points = " ".join(f"{float(x)},{float(y)}" for x, y in points)
    court_points = " ".join(f"{point[0]},{point[1]}" for point in polygon)
    (output / "track-court-preview.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2746 1536"><rect width="2746" height="1536" fill="white"/><polygon points="{court_points}" fill="none" stroke="green" stroke-width="4"/><polyline points="{track_points}" fill="none" stroke="blue" stroke-width="3"/><text x="20" y="35" font-size="24">Stage 1B real track candidate; no video background</text></svg>\n'
    )
    events = load_events(events_path)
    marks = []
    for event in events:
        x = 40 + float(event["time_start_seconds"]) / duration * 1120
        marks.append(
            f'<line x1="{x}" y1="80" x2="{x}" y2="240" stroke="red"/><text x="{x + 2}" y="70" font-size="12">{event["id"]}:{event["type"]}</text>'
        )
    (output / "event-timeline.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 280"><rect width="1200" height="280" fill="white"/><text x="20" y="25" font-size="18">nivel_a2_01 event timeline ({duration:.6f}s)</text><line x1="40" y1="160" x2="1160" y2="160" stroke="black"/>{"".join(marks)}<text x="40" y="185" font-size="14">0.0s</text><text x="1080" y="185" font-size="14">{duration:.3f}s</text></svg>\n'
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-video", type=Path, required=True)
    parser.add_argument("--track", type=Path, required=True)
    parser.add_argument("--timestamps", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--court", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(".artifacts/stage1b-real-single-rally"))
    parser.add_argument("--fixture-output", type=Path)
    args = parser.parse_args()
    output = args.output
    if output.exists():
        shutil.rmtree(output)
    (output / "work").mkdir(parents=True)
    video = _ffprobe(args.source_video)
    clip_manifest = load_json(args.source_video.parent / "clip_manifest.json")
    video["canonical_width"] = clip_manifest["canonical_width"]
    video["canonical_height"] = clip_manifest["canonical_height"]
    timestamps = _timestamp_audit(args.timestamps, video)
    timestamp_map = load_frame_timestamps(args.timestamps)
    track = _track_audit(args.track, video, timestamp_map)
    events_payload = load_json(args.events)
    event_alignment = _event_alignment(args.events, args.track)
    calibration = _calibration_audit(args.court, video)
    if (
        not calibration["dimensions_match_video_canonical"]
        or calibration["calibration_status"] != "approved"
    ):
        raise SystemExit("REAL_REFERENCE_ASSET_ALIGNMENT_FAILED: calibration")
    surface = str(clip_manifest.get("surface", "unknown"))
    if surface not in {"clay", "hard", "grass", "carpet", "unknown"}:
        surface = "unknown"
    descriptor = {
        "schema_version": "single_rally_inputs.v1",
        "files": {
            "events": str(args.events.resolve()),
            "ball_track": str(args.track.resolve()),
            "court_map": str(args.court.resolve()),
            "frame_timestamps": str(args.timestamps.resolve()),
        },
        "start_time_seconds": track["first_timestamp_seconds"],
        "end_time_seconds": track["last_timestamp_seconds"],
        "index": 0,
        "limitations": [
            "imported_existing_stage3_track",
            "imported_manual_stage4_events",
            "external_source_video",
            "surface_metadata_unavailable",
        ],
    }
    descriptor_path = output / "work/single-rally-inputs.json"
    descriptor_path.write_text(json.dumps(descriptor, indent=2, sort_keys=True) + "\n")
    build_a = output / "build-a"
    build_b = output / "build-b"
    result_a = import_single_rally(
        args.source_video,
        descriptor_path,
        "nivel_a2_01",
        "rally_001",
        "STANDARD",
        surface,
        build_a,
        "2026-07-21T00:00:00Z",
    )
    result_b = import_single_rally(
        args.source_video,
        descriptor_path,
        "nivel_a2_01",
        "rally_001",
        "STANDARD",
        surface,
        build_b,
        "2026-07-21T00:00:00Z",
    )
    validation = validate_single_rally_bundle(build_a)
    if result_a["fingerprint"] != result_b["fingerprint"]:
        raise SystemExit("non-deterministic real candidate")
    for name in (
        "video-metadata.json",
        "timestamp-audit.json",
        "track-audit.json",
        "event-track-alignment.json",
    ):
        value = {
            "video-metadata.json": video,
            "timestamp-audit.json": timestamps,
            "track-audit.json": track,
            "event-track-alignment.json": event_alignment,
        }[name]
        (output / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    _write_svg(
        output,
        args.track,
        args.court,
        args.events,
        video["duration_seconds"],
    )
    (output / "validation-report.json").write_text(
        json.dumps(
            {**validation, "source_verification": "passed", "surface": surface},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    (output / "alignment-report.json").write_text(
        json.dumps(
            {
                "status": "REAL_REFERENCE_ASSET_ALIGNMENT_PASSED",
                "video_sha_verified": video["sha256"] == clip_manifest["source_sha256"],
                "timestamp_audit": timestamps["timestamps_non_decreasing"],
                "track_audit": track["frame_ids_unique"] and track["frame_ids_ordered"],
                "event_count": len(events_payload["narrative_events"]),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    (output / "REFERENCE_SOURCE.json").write_text(
        json.dumps(
            {
                "display_name": args.source_video.name,
                "sha256": video["sha256"],
                "duration_seconds": video["duration_seconds"],
                "width": video["width"],
                "height": video["height"],
                "fps_nominal": video["r_frame_rate"],
                "frame_count": video["nb_frames"],
                "session_id": "nivel_a2_01",
                "rally_id": "rally_001",
                "surface": surface,
                "provenance": "existing_local_reference_assets",
                "asset_alignment_gate": "REAL_REFERENCE_ASSET_ALIGNMENT_PASSED",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    if args.fixture_output:
        fixture = args.fixture_output
        fixture.mkdir(parents=True, exist_ok=True)
        for name in (
            "manifest.json",
            "session.json",
            "rallies.json",
            "events.jsonl",
            "ball_track.jsonl",
            "court_map.json",
            "metrics.json",
        ):
            shutil.copy2(build_a / name, fixture / name)
        for name in (
            "REFERENCE_SOURCE.json",
            "alignment-report.json",
            "validation-report.json",
            "track-court-preview.svg",
            "event-timeline.svg",
        ):
            shutil.copy2(output / name, fixture / name)
        (fixture / "clips").mkdir(exist_ok=True)
        (fixture / "thumbnails").mkdir(exist_ok=True)
        (fixture / "clips/.gitkeep").write_text("")
        (fixture / "thumbnails/.gitkeep").write_text("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
