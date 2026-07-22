#!/usr/bin/env python3
"""Audit existing reference assets and publish a real Stage 1B candidate.

The script only hashes/probes existing files and transports their serialized
outputs. It never runs detection, tracking, inference, models or video decode.
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

EXPECTED_VIDEO_SHA = "e2a05a8eda9be4d821ae1acc60355c7c0403e450ac0febd6bb3c6a62e0aa5774"
PASSED = "REAL_REFERENCE_ASSET_ALIGNMENT_PASSED"
PARTIAL = "REAL_REFERENCE_ASSET_ALIGNMENT_PARTIAL"
FAILED = "REAL_REFERENCE_ASSET_ALIGNMENT_FAILED"
MARKER = ".stage1b-output-marker"
FIXTURE_STAGING_MARKER = ".stage1b-fixture-staging-marker"
FIXTURE_STAGING_MARKER_CONTENT = "stage1b-real-single-rally-fixture-staging-v1"
CANONICAL_SOURCES = {"detected": "smoothed", "missing": "missing", "interpolated": "interpolated"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _expected_fixture_path() -> Path:
    return _repo_root() / "tests" / "fixtures" / "product" / "real_single_rally_nivel_a2_01"


def _protected_fixture_output(path: Path) -> Path:
    """Allow publication only to the single Stage 1B fixture directory."""
    repo = _repo_root().resolve()
    expected = _expected_fixture_path().resolve()
    raw = repo / path if not path.is_absolute() else path
    if ".." in raw.parts:
        raise SystemExit("--fixture-output parent traversal rejected")
    cursor = raw
    while cursor != cursor.parent:
        if cursor.is_symlink():
            raise SystemExit("--fixture-output symlink rejected")
        if cursor == repo:
            break
        cursor = cursor.parent
    resolved = raw.resolve()
    if resolved != expected:
        raise SystemExit(f"--fixture-output must equal {expected}")
    if expected.parent.is_symlink():
        raise SystemExit("--fixture-output parent symlink rejected")
    return expected


def _regular_input(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise SystemExit(f"input must be a non-symlink file: {path}")
    return path.resolve()


def _ffprobe(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "format=format_name,duration,start_time:stream=codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,time_base,start_time:stream_tags=rotate:stream_side_data=side_data_type,rotation",
        "-of",
        "json",
        str(path),
    ]
    payload = json.loads(subprocess.check_output(command, text=True))
    stream = (payload.get("streams") or [{}])[0]
    fmt = payload.get("format") or {}
    side_data = stream.get("side_data_list") or []
    rotation = None
    rotation_source = "unknown"
    for item in side_data:
        if item.get("rotation") is not None:
            rotation = float(item["rotation"])
            rotation_source = "ffprobe.side_data_list"
            break
    if rotation is None and (stream.get("tags") or {}).get("rotate") is not None:
        rotation = float(stream["tags"]["rotate"])
        rotation_source = "ffprobe.stream.tags.rotate"
    return {
        "filename": path.name,
        "format": fmt.get("format_name"),
        "duration_seconds": float(fmt["duration"]),
        "encoded_width": int(stream["width"]),
        "encoded_height": int(stream["height"]),
        "codec": stream.get("codec_name"),
        "r_frame_rate": stream.get("r_frame_rate"),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "nb_frames": int(stream["nb_frames"])
        if stream.get("nb_frames") not in (None, "N/A")
        else None,
        "time_base": stream.get("time_base"),
        "start_time": stream.get("start_time", fmt.get("start_time")),
        "rotation_degrees": rotation,
        "rotation_source": rotation_source,
        "side_data_list": side_data,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _timestamp_audit(path: Path, video: dict[str, Any]) -> dict[str, Any]:
    frames = load_json(path)["frames"]
    ids = [int(item["frame_id"]) for item in frames]
    times = [float(item["timestamp_seconds"]) for item in frames]
    deltas = [right - left for left, right in zip(times, times[1:])]
    sorted_deltas = sorted(deltas)
    p95_index = min(len(sorted_deltas) - 1, math.ceil(0.95 * len(sorted_deltas)) - 1)
    return {
        "display_name": path.name,
        "schema_version": load_json(path).get("schema_version"),
        "frame_count": len(frames),
        "expected_frame_count": video["nb_frames"],
        "frame_ids": ids,
        "frame_ids_unique": len(set(ids)) == len(ids),
        "frame_ids_contiguous": ids == list(range(len(ids))),
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
        "missing_frames": sorted(set(range(max(ids) + 1)) - set(ids)),
        "duplicate_frames": len(ids) - len(set(ids)),
        "timing_mode": load_json(path).get("timing_mode"),
    }


def _track_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _track_audit(path: Path, video: dict[str, Any], timestamps: dict[int, float]) -> dict[str, Any]:
    rows = _track_rows(path)
    frames = [int(row["frame_id"]) for row in rows]
    times = [float(row["timestamp_seconds"]) for row in rows]
    canonical_width = {int(row["canonical_width"]) for row in rows}
    canonical_height = {int(row["canonical_height"]) for row in rows}
    records = []
    for row in rows:
        declared = row.get("source", "raw")
        source = CANONICAL_SOURCES.get(declared, "raw")
        detected = row.get("detected_raw", "false").lower() == "true"
        x = row.get("x_smooth")
        y = row.get("y_smooth")
        x_value = float(x) if x not in (None, "") else None
        y_value = float(y) if y not in (None, "") else None
        if detected and (
            x_value is None or y_value is None or not math.isfinite(x_value + y_value)
        ):
            raise ValueError(f"non-finite visible point at frame {row['frame_id']}")
        records.append(
            {
                "frame_id": int(row["frame_id"]),
                "timestamp_seconds": float(row["timestamp_seconds"]),
                "source": source,
                "declared_source": declared,
                "visible": detected,
                "pixel_x": x_value,
                "pixel_y": y_value,
            }
        )
    visible = [record["visible"] for record in records]
    missing_run = max_run = 0
    for value in visible:
        if value:
            missing_run = 0
        else:
            missing_run += 1
            max_run = max(max_run, missing_run)
    canonical_width_value = canonical_width.pop() if len(canonical_width) == 1 else None
    canonical_height_value = canonical_height.pop() if len(canonical_height) == 1 else None
    bounds_ok = all(
        not record["visible"]
        or (
            0 <= record["pixel_x"] < video["canonical_width"]
            and 0 <= record["pixel_y"] < video["canonical_height"]
        )
        for record in records
    )
    return {
        "display_name": path.name,
        "format": "CSV",
        "sha256": sha256_file(path),
        "observations": len(rows),
        "frame_ids": frames,
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
        "interpolated_observations": sum(record["source"] == "interpolated" for record in records),
        "missing_observations": sum(record["source"] == "missing" for record in records),
        "source_counts": {
            source: sum(record["source"] == source for record in records)
            for source in {record["source"] for record in records}
        },
        "confidence_available": all(row.get("confidence") not in (None, "") for row in rows),
        "max_non_visible_run": max_run,
        "canonical_width": canonical_width_value,
        "canonical_height": canonical_height_value,
        "canonical_dimensions_consistent": canonical_width_value is not None
        and canonical_height_value is not None,
        "bounds_ok": bounds_ok,
        "records": records,
    }


def _event_audit(path: Path, track: dict[str, Any], video: dict[str, Any]) -> dict[str, Any]:
    events = load_events(path)
    records = []
    for event in events:
        frame = int(event.get("frame_start", event.get("frame_id")))
        timestamp = float(event.get("time_start_seconds", event.get("timestamp_seconds")))
        raw_type = str(event.get("type", event.get("event_type", "unknown")))
        event_type = {
            "hit": "contact",
            "contact": "contact",
            "bounce": "bounce",
            "serve": "serve",
            "out": "out",
        }.get(raw_type, "unknown")
        records.append(
            {
                "event_id": event.get("id", event.get("event_id")),
                "event_type": event_type,
                "frame_id": frame,
                "timestamp_seconds": timestamp,
            }
        )
    return {
        "display_name": path.name,
        "sha256": sha256_file(path),
        "event_count": len(records),
        "event_ids_unique": len({record["event_id"] for record in records}) == len(records),
        "events_ordered": [record["frame_id"] for record in records]
        == sorted(record["frame_id"] for record in records),
        "events_in_range": all(
            0 <= record["frame_id"] < video["nb_frames"]
            and 0 <= record["timestamp_seconds"] <= video["duration_seconds"]
            for record in records
        ),
        "records": records,
    }


def _calibration_audit(path: Path, video: dict[str, Any]) -> dict[str, Any]:
    payload = load_json(path)
    dimensions = payload["frame_dimensions"]
    corners = payload["court_corners_pixel"]
    outer = [corners.get(name) for name in ("far_left", "far_right", "near_right", "near_left")]
    matrix = payload.get("H_pixel_to_court")
    shape_ok = (
        isinstance(matrix, list)
        and len(matrix) == 3
        and all(isinstance(row, list) and len(row) == 3 for row in matrix)
    )
    determinant = None
    if shape_ok:
        determinant = (
            matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
            - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
            + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
        )
    corners_valid = all(
        isinstance(point, list)
        and len(point) == 2
        and all(math.isfinite(float(value)) for value in point)
        and 0 <= float(point[0]) < video["canonical_width"]
        and 0 <= float(point[1]) < video["canonical_height"]
        for point in outer
    )
    homography_finite = shape_ok and all(
        math.isfinite(float(value)) for row in matrix for value in row
    )
    provenance = payload.get("provenance") or "existing_court_calibration"
    return {
        "display_name": path.name,
        "sha256": sha256_file(path),
        "dimensions": dimensions,
        "dimensions_match_canonical": dimensions
        == {"width": video["canonical_width"], "height": video["canonical_height"]},
        "outer_corner_count": sum(point is not None for point in outer),
        "corners_valid": corners_valid,
        "orientation_passed": payload.get("orientation_validation", {}).get("passed", False),
        "homography_shape": [len(matrix), len(matrix[0])] if shape_ok else None,
        "homography_finite": homography_finite,
        "homography_determinant": determinant,
        "homography_non_singular": homography_finite and determinant != 0,
        "layout": payload.get("layout", "doubles"),
        "provenance": provenance,
        "non_synthetic_provenance": provenance not in {"", "synthetic_contract_fixture"},
        "calibration_status": "approved"
        if dimensions == {"width": video["canonical_width"], "height": video["canonical_height"]}
        and corners_valid
        and payload.get("orientation_validation", {}).get("passed", False)
        and homography_finite
        and determinant != 0
        and provenance not in {"", "synthetic_contract_fixture"}
        else "partial",
    }


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {"name": name, "status": "passed" if passed else "failed", "detail": detail}


def evaluate_asset_alignment(
    video: dict[str, Any],
    timestamps: dict[str, Any],
    track: dict[str, Any],
    events: dict[str, Any],
    calibration: dict[str, Any],
    asset_hashes: dict[str, Any],
    clip_manifest: dict[str, Any],
    expected_video_sha: str = EXPECTED_VIDEO_SHA,
) -> dict[str, Any]:
    frame_ids = timestamps["frame_ids"]
    track_ids = track["frame_ids"]
    event_frames = [record["frame_id"] for record in events["records"]]
    checks = [
        _check(
            "video_sha_expected",
            video["sha256"] == expected_video_sha,
            "source SHA matches expected reference",
        ),
        _check(
            "video_sha_manifest",
            video["sha256"] == clip_manifest.get("source_sha256"),
            "source SHA matches clip manifest",
        ),
        _check(
            "frame_count_matches_timestamps",
            video["nb_frames"] is not None and video["nb_frames"] == timestamps["frame_count"],
            "ffprobe frame count equals timestamp records",
        ),
        _check(
            "timestamps_unique_contiguous",
            timestamps["frame_ids_unique"] and timestamps["frame_ids_contiguous"],
            "timestamp frame IDs are unique and contiguous",
        ),
        _check(
            "timestamps_finite_nondecreasing",
            timestamps["timestamps_finite"]
            and timestamps["timestamps_non_decreasing"]
            and timestamps["negative_timestamps"] == 0,
            "timestamps are finite, non-negative and ordered",
        ),
        _check(
            "timestamp_first_frame", timestamps["first_frame"] == 0, "first timestamp frame is zero"
        ),
        _check(
            "timestamp_last_frame",
            video["nb_frames"] is not None and timestamps["last_frame"] == video["nb_frames"] - 1,
            "last timestamp frame reaches video end",
        ),
        _check(
            "duration_compatible",
            abs(timestamps["duration_delta_seconds"]) <= 0.05,
            "timestamp coverage is compatible with video duration",
        ),
        _check(
            "track_timestamp_frame_ids",
            track_ids == frame_ids,
            "track covers exactly the timestamp frame IDs",
        ),
        _check(
            "track_ordered_unique",
            track["frame_ids_unique"] and track["frame_ids_ordered"],
            "track IDs are ordered and unique",
        ),
        _check(
            "track_in_video",
            not track["out_of_video_frames"],
            "no track frame lies outside the video",
        ),
        _check(
            "track_canonical_dimensions",
            track["canonical_dimensions_consistent"]
            and track["canonical_width"] == video["canonical_width"]
            and track["canonical_height"] == video["canonical_height"],
            "track canonical dimensions are consistent",
        ),
        _check("event_ids_unique", events["event_ids_unique"], "event IDs are unique"),
        _check("events_ordered", events["events_ordered"], "events are ordered"),
        _check(
            "events_in_range", events["events_in_range"], "events are within video frame/time range"
        ),
        _check(
            "events_related_to_track",
            all(frame in set(track_ids) for frame in event_frames),
            "each event has a matching track frame",
        ),
        _check(
            "calibration_dimensions",
            calibration["dimensions_match_canonical"],
            "calibration uses canonical dimensions",
        ),
        _check(
            "calibration_corners",
            calibration["corners_valid"],
            "four outer calibration corners are valid",
        ),
        _check(
            "calibration_homography",
            calibration["homography_shape"] == [3, 3]
            and calibration["homography_finite"]
            and calibration["homography_non_singular"],
            "homography is finite 3x3 and non-singular",
        ),
        _check(
            "calibration_provenance",
            calibration["non_synthetic_provenance"],
            "calibration provenance is non-synthetic",
        ),
        _check(
            "asset_hashes_recorded",
            len(asset_hashes) == 6 and all(item.get("sha256") for item in asset_hashes.values()),
            "six selected asset hashes are recorded",
        ),
        _check(
            "asset_identity",
            clip_manifest.get("clip_id") == "nivel_a2_01"
            and clip_manifest.get("source_filename") == video["filename"],
            "all assets identify nivel_a2_01",
        ),
    ]
    failed = [item for item in checks if item["status"] == "failed"]
    gate = FAILED if failed else PASSED
    return {
        "gate_derived": gate,
        "video_sha_verified": video["sha256"] == expected_video_sha
        and video["sha256"] == clip_manifest.get("source_sha256"),
        "checks": checks,
        "checks_executed": len(checks),
        "checks_passed": len(checks) - len(failed),
        "checks_partial": 0,
        "checks_failed": len(failed),
        "blockers": [item["name"] for item in failed],
        "warnings": [],
    }


def _event_alignment(events: dict[str, Any], track: dict[str, Any]) -> dict[str, Any]:
    rows = {record["frame_id"]: record for record in track["records"]}
    aligned = []
    for event in events["records"]:
        matching = rows.get(event["frame_id"])
        if matching is None:
            matching = min(
                track["records"], key=lambda row: abs(row["frame_id"] - event["frame_id"])
            )
            quality = "nearest_detected" if matching["source"] == "smoothed" else "invalid"
        elif matching["source"] == "smoothed":
            quality = "detected_exact"
        elif matching["source"] == "interpolated":
            quality = "interpolated_exact"
        else:
            quality = "missing_exact"
        aligned.append(
            {
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "frame_id": event["frame_id"],
                "timestamp_seconds": event["timestamp_seconds"],
                "matching_track_frame": matching["frame_id"],
                "frame_delta": matching["frame_id"] - event["frame_id"],
                "timestamp_delta_seconds": matching["timestamp_seconds"]
                - event["timestamp_seconds"],
                "track_observation_source": matching["source"],
                "track_visible": matching["visible"],
                "track_pixel_x": matching["pixel_x"],
                "track_pixel_y": matching["pixel_y"],
                "event_pixel_available": False,
                "pixel_distance": None,
                "alignment_quality": quality,
            }
        )
    summary = {
        quality: sum(item["alignment_quality"] == quality for item in aligned)
        for quality in (
            "detected_exact",
            "interpolated_exact",
            "missing_exact",
            "nearest_detected",
            "invalid",
        )
    }
    return {
        "event_count": len(aligned),
        "aligned_event_count": sum(item["alignment_quality"] != "invalid" for item in aligned),
        "summary": summary,
        "maximum_frame_delta": max(abs(item["frame_delta"]) for item in aligned),
        "maximum_timestamp_delta_seconds": max(
            abs(item["timestamp_delta_seconds"]) for item in aligned
        ),
        "events": aligned,
    }


def _write_svg(
    output: Path,
    track: dict[str, Any],
    court_path: Path,
    events: dict[str, Any],
    canonical_width: int,
    canonical_height: int,
    duration: float,
) -> int:
    court = load_json(court_path)
    corners = court["court_corners_pixel"]
    polygon = [corners[name] for name in ("far_left", "far_right", "near_right", "near_left")]
    segments: list[tuple[str, list[dict[str, Any]]]] = []
    current: list[dict[str, Any]] = []
    current_source = None
    previous_frame = None
    for row in track["records"]:
        source = (
            row["source"] if row["pixel_x"] is not None and row["pixel_y"] is not None else None
        )
        if (
            source is None
            or (previous_frame is not None and row["frame_id"] != previous_frame + 1)
            or (current_source is not None and source != current_source)
        ):
            if len(current) >= 2:
                segments.append((current_source, current))
            current = []
            current_source = None
        if source is not None:
            current.append(row)
            current_source = source
        previous_frame = row["frame_id"]
    if len(current) >= 2:
        segments.append((current_source, current))
    lines = []
    for index, (source, rows) in enumerate(segments):
        points = " ".join(f"{row['pixel_x']},{row['pixel_y']}" for row in rows)
        dash = ' stroke-dasharray="12 8"' if source == "interpolated" else ""
        lines.append(
            f'<polyline id="track-segment-{index}" data-source="{source}" points="{points}" fill="none" stroke="blue" stroke-width="3"{dash}/>'
        )
    marks = []
    for event in events["records"]:
        row = next(item for item in track["records"] if item["frame_id"] == event["frame_id"])
        if row["pixel_x"] is None:
            continue
        color = {"contact": "red", "bounce": "orange", "serve": "purple"}.get(
            event["event_type"], "black"
        )
        suffix = " (interpolated)" if row["source"] == "interpolated" else ""
        marks.append(
            f'<circle cx="{row["pixel_x"]}" cy="{row["pixel_y"]}" r="9" fill="{color}" data-event-source="{row["source"]}"/><text x="{row["pixel_x"] + 10}" y="{row["pixel_y"]}" font-size="16">{event["event_id"]}:{event["event_type"]}{suffix}</text>'
        )
    court_points = " ".join(f"{point[0]},{point[1]}" for point in polygon)
    legend = '<g font-size="18"><text x="20" y="30">solid = smoothed/detected</text><text x="20" y="55">dashed = interpolated</text><text x="20" y="80" fill="red">contact</text><text x="110" y="80" fill="orange">bounce</text><text x="210" y="80" fill="purple">serve</text></g>'
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canonical_width} {canonical_height}"><rect width="{canonical_width}" height="{canonical_height}" fill="white"/><polygon points="{court_points}" fill="none" stroke="green" stroke-width="4"/>{"".join(lines)}{"".join(marks)}{legend}<text x="20" y="{canonical_height - 20}" font-size="20">Stage 1B real track candidate; canonical analysis pixels; no video background</text></svg>\n'
    (output / "track-court-preview.svg").write_text(svg, encoding="utf-8")
    marks = []
    for event in events["records"]:
        x = 40 + event["timestamp_seconds"] / duration * 1120
        marks.append(
            f'<line x1="{x}" y1="80" x2="{x}" y2="240" stroke="red"/><text x="{x + 2}" y="70" font-size="12">{event["event_id"]}:{event["event_type"]}</text>'
        )
    timeline = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 280"><rect width="1200" height="280" fill="white"/><text x="20" y="25" font-size="18">nivel_a2_01 event timeline ({duration:.6f}s)</text><line x1="40" y1="160" x2="1160" y2="160" stroke="black"/>{"".join(marks)}<text x="40" y="185" font-size="14">0.0s</text><text x="1080" y="185" font-size="14">{duration:.3f}s</text></svg>\n'
    (output / "event-timeline.svg").write_text(timeline, encoding="utf-8")
    return len(segments)


def _protected_output(path: Path) -> Path:
    artifacts = (_repo_root() / ".artifacts").resolve()
    raw_candidate = artifacts / path if not path.is_absolute() else path
    if ".." in raw_candidate.parts:
        raise SystemExit("--output parent traversal rejected")
    raw_cursor = raw_candidate
    while raw_cursor != artifacts and raw_cursor != raw_cursor.parent:
        if raw_cursor.is_symlink():
            raise SystemExit("--output symlink rejected")
        raw_cursor = raw_cursor.parent
    candidate = raw_candidate.resolve()
    if candidate == artifacts or artifacts not in candidate.parents:
        raise SystemExit("--output must be a child of .artifacts")
    cursor = candidate
    while cursor != artifacts:
        if cursor.is_symlink():
            raise SystemExit("--output symlink rejected")
        cursor = cursor.parent
    if candidate.exists():
        marker = candidate / MARKER
        if (
            not marker.is_file()
            or marker.read_text(encoding="utf-8") != "stage1b-real-single-rally-output-v1\n"
        ):
            raise SystemExit("existing --output was not generated by this script")
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True)
    (candidate / MARKER).write_text("stage1b-real-single-rally-output-v1\n", encoding="utf-8")
    return candidate


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _owned_marker(path: Path) -> bool:
    return path.is_file() and path.read_text(encoding="utf-8") == FIXTURE_STAGING_MARKER_CONTENT


def _contains_symlink(path: Path) -> bool:
    return (
        any(item.is_symlink() for item in path.rglob("*")) if path.is_dir() else path.is_symlink()
    )


def _remove_owned_tree(path: Path) -> None:
    if path.exists() or path.is_symlink():
        if path.is_symlink() or _contains_symlink(path):
            raise SystemExit(f"symlink found in protected Stage 1B path: {path}")
        if not _owned_marker(path / FIXTURE_STAGING_MARKER):
            raise SystemExit(f"refusing to remove unowned Stage 1B path: {path}")
        shutil.rmtree(path)


def _publish_fixture(fixture: Path, output: Path, bundle: Path) -> None:
    fixture = _protected_fixture_output(fixture)
    parent = fixture.parent
    staging = parent / ".real_single_rally_nivel_a2_01.stage1b-staging"
    backup = parent / ".real_single_rally_nivel_a2_01.stage1b-backup"
    if staging.exists() or staging.is_symlink():
        _remove_owned_tree(staging)
    if backup.exists() or backup.is_symlink():
        _remove_owned_tree(backup)
    staging.mkdir(parents=False)
    (staging / FIXTURE_STAGING_MARKER).write_text(FIXTURE_STAGING_MARKER_CONTENT, encoding="utf-8")
    bundle_names = (
        "manifest.json",
        "session.json",
        "rallies.json",
        "events.jsonl",
        "ball_track.jsonl",
        "court_map.json",
        "metrics.json",
    )
    report_names = (
        "REFERENCE_SOURCE.json",
        "alignment-report.json",
        "video-metadata.json",
        "timestamp-audit.json",
        "track-audit.json",
        "event-track-alignment.json",
        "calibration-audit.json",
        "asset-hashes.json",
        "validation-report.json",
        "track-court-preview.svg",
        "event-timeline.svg",
    )
    try:
        for name in bundle_names:
            source = bundle / name
            if source.is_symlink() or not source.is_file():
                raise RuntimeError(f"missing or symlinked bundle file: {source}")
            shutil.copy2(source, staging / name)
        for name in report_names:
            source = output / name
            if source.is_symlink() or not source.is_file():
                raise RuntimeError(f"missing or symlinked report file: {source}")
            shutil.copy2(source, staging / name)
        (staging / "clips").mkdir()
        (staging / "thumbnails").mkdir()
        (staging / "clips/.gitkeep").write_text("", encoding="utf-8")
        (staging / "thumbnails/.gitkeep").write_text("", encoding="utf-8")
        required = [staging / name for name in (*bundle_names, *report_names)]
        if not all(item.is_file() and not item.is_symlink() for item in required):
            raise RuntimeError("staging validation failed")
        if fixture.exists():
            if _contains_symlink(fixture):
                raise RuntimeError("symlink found in existing Stage 1B fixture")
            fixture.rename(backup)
        try:
            staging.rename(fixture)
            (fixture / FIXTURE_STAGING_MARKER).unlink()
        except Exception:
            if backup.exists() and not fixture.exists():
                backup.rename(fixture)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if staging.exists() or staging.is_symlink():
            _remove_owned_tree(staging)
        if backup.exists() and not fixture.exists():
            backup.rename(fixture)
        raise


def _require_publishable_alignment(alignment: dict[str, Any]) -> None:
    if alignment.get("gate_derived") != PASSED:
        raise SystemExit(
            f"fixture publication blocked by alignment gate: {alignment.get('gate_derived')}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-video", type=Path, required=True)
    parser.add_argument("--track", type=Path, required=True)
    parser.add_argument("--timestamps", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--court", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("stage1b-real-single-rally"))
    parser.add_argument("--fixture-output", type=Path)
    args = parser.parse_args()
    source_video = _regular_input(args.source_video)
    track_path = _regular_input(args.track)
    timestamps_path = _regular_input(args.timestamps)
    events_path = _regular_input(args.events)
    court_path = _regular_input(args.court)
    clip_manifest_path = _regular_input(source_video.parent / "clip_manifest.json")
    clip_manifest = load_json(clip_manifest_path)
    video = _ffprobe(source_video)
    video["canonical_width"] = int(clip_manifest["canonical_width"])
    video["canonical_height"] = int(clip_manifest["canonical_height"])
    if (
        video["rotation_degrees"] is None
        and clip_manifest.get("container_rotation_degrees") is not None
    ):
        video["rotation_degrees"] = float(clip_manifest["container_rotation_degrees"])
        video["rotation_source"] = "clip_manifest"
    video["canonical_transform"] = clip_manifest.get("canonical_transform", "unknown")
    timestamps = _timestamp_audit(timestamps_path, video)
    timestamp_map = load_frame_timestamps(timestamps_path)
    track = _track_audit(track_path, video, timestamp_map)
    events = _event_audit(events_path, track, video)
    calibration = _calibration_audit(court_path, video)
    asset_hashes = {
        "video": {"display_name": source_video.name, "sha256": video["sha256"]},
        "stage3_track": {"display_name": track_path.name, "sha256": track["sha256"]},
        "frame_timestamps": {
            "display_name": timestamps_path.name,
            "sha256": sha256_file(timestamps_path),
        },
        "stage4_events": {"display_name": events_path.name, "sha256": events["sha256"]},
        "court_calibration": {"display_name": court_path.name, "sha256": calibration["sha256"]},
        "clip_manifest": {
            "display_name": clip_manifest_path.name,
            "sha256": sha256_file(clip_manifest_path),
        },
    }
    alignment = evaluate_asset_alignment(
        video, timestamps, track, events, calibration, asset_hashes, clip_manifest
    )
    _require_publishable_alignment(alignment)
    output = _protected_output(args.output)
    surface = clip_manifest.get("surface", "unknown")
    if surface not in {"clay", "hard", "grass", "carpet", "unknown"}:
        surface = "unknown"
    descriptor = {
        "schema_version": "single_rally_inputs.v1",
        "files": {
            "events": str(events_path),
            "ball_track": str(track_path),
            "court_map": str(court_path),
            "frame_timestamps": str(timestamps_path),
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
    descriptor_path.parent.mkdir()
    _write_json(descriptor_path, descriptor)
    build_a = output / "build-a"
    build_b = output / "build-b"
    result_a = import_single_rally(
        source_video,
        descriptor_path,
        "nivel_a2_01",
        "rally_001",
        "STANDARD",
        surface,
        build_a,
        "2026-07-21T00:00:00Z",
    )
    result_b = import_single_rally(
        source_video,
        descriptor_path,
        "nivel_a2_01",
        "rally_001",
        "STANDARD",
        surface,
        build_b,
        "2026-07-21T00:00:00Z",
    )
    validation = validate_single_rally_bundle(build_a)
    if result_a["fingerprint"] != result_b["fingerprint"] or _bundle_files(
        build_a
    ) != _bundle_files(build_b):
        raise SystemExit("non-deterministic real candidate")
    preview_segments = _write_svg(
        output,
        track,
        court_path,
        events,
        video["canonical_width"],
        video["canonical_height"],
        video["duration_seconds"],
    )
    _write_json(
        output / "video-metadata.json",
        {
            key: value
            for key, value in video.items()
            if key not in {"canonical_width", "canonical_height"}
        }
        | {
            "canonical_width": video["canonical_width"],
            "canonical_height": video["canonical_height"],
        },
    )
    _write_json(
        output / "timestamp-audit.json",
        {key: value for key, value in timestamps.items() if key != "frame_ids"},
    )
    _write_json(
        output / "track-audit.json",
        {key: value for key, value in track.items() if key not in {"frame_ids", "records"}},
    )
    alignment_details = _event_alignment(events, track)
    _write_json(output / "event-track-alignment.json", alignment_details)
    _write_json(output / "calibration-audit.json", calibration)
    _write_json(output / "asset-hashes.json", asset_hashes)
    _write_json(
        output / "validation-report.json",
        {
            **validation,
            "source_verification": "passed",
            "surface": surface,
            "preview_segments": preview_segments,
        },
    )
    _write_json(
        output / "alignment-report.json",
        {
            **alignment,
            "event_track_summary": alignment_details["summary"],
            "references": [
                "video-metadata.json",
                "timestamp-audit.json",
                "track-audit.json",
                "event-track-alignment.json",
                "calibration-audit.json",
                "asset-hashes.json",
            ],
        },
    )
    _write_json(
        output / "REFERENCE_SOURCE.json",
        {
            "assets": asset_hashes,
            "duration_seconds": video["duration_seconds"],
            "encoded_width": video["encoded_width"],
            "encoded_height": video["encoded_height"],
            "canonical_width": video["canonical_width"],
            "canonical_height": video["canonical_height"],
            "rotation_degrees": video["rotation_degrees"],
            "rotation_source": video["rotation_source"],
            "canonical_transform": video["canonical_transform"],
            "coordinate_space_used_by_track": "canonical_analysis_pixels",
            "coordinate_space_used_by_court": "canonical_analysis_pixels",
            "coordinate_transform_status": "canonical_transform_verified",
            "fps_nominal": video["r_frame_rate"],
            "frame_count": video["nb_frames"],
            "session_id": "nivel_a2_01",
            "rally_id": "rally_001",
            "surface": surface,
            "court_layout": calibration["layout"],
            "provenance": "existing_local_reference_assets",
            "asset_alignment_gate": alignment["gate_derived"],
        },
    )
    if args.fixture_output:
        fixture_output = _protected_fixture_output(args.fixture_output)
        _publish_fixture(fixture_output, output, build_a)
    return 0


def _bundle_files(path: Path) -> dict[str, tuple[int, str]]:
    names = (
        "manifest.json",
        "session.json",
        "rallies.json",
        "events.jsonl",
        "ball_track.jsonl",
        "court_map.json",
        "metrics.json",
    )
    return {name: (path.joinpath(name).stat().st_size, sha256_file(path / name)) for name in names}


if __name__ == "__main__":
    raise SystemExit(main())
