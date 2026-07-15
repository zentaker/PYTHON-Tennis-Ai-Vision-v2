"""Normalize and render the human Stage 4 annotation for the canonical A2 clip."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import cv2

from src.events.event_loader import load_annotation, run_stage_4
from src.events.render_events_contact_sheet import render_events_contact_sheet
from src.events.render_events_overlay import render_events_overlay
from src.events.render_events_timeline import render_events_timeline
from src.project.clip_manifest import ClipManifest
from src.video.canonical_frames import probe_frame_timestamps, timestamp_intervals
from src.video.frame_timestamps import FrameTimestampSidecar, validate_sidecar_against_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLIP_ID = "nivel_a2_01"
CLIP_DIR = PROJECT_ROOT / "data" / "clips" / CLIP_ID
OUTPUT_DIR = PROJECT_ROOT / "outputs" / CLIP_ID / "stage_4"


def sha256_file(path: Path) -> str:
    """Hash one immutable input or generated artifact."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decode_overlay_endpoints(path: Path) -> dict[str, object]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open generated overlay: {path}")
    count = 0
    first_readable = False
    last_readable = False
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if count == 0:
            first_readable = frame is not None and frame.size > 0
        last_readable = frame is not None and frame.size > 0
        count += 1
    capture.release()
    return {
        "decoded_frames": count,
        "first_frame_readable": first_readable,
        "last_frame_readable": last_readable,
    }


def _validate_normalized_events(
    annotation: dict[str, Any],
    normalized: dict[str, Any],
) -> None:
    source_events = annotation["narrative_events"]
    output_events = normalized["events"]
    if len(source_events) != len(output_events):
        raise RuntimeError("Normalized output changed the event count")
    preserved_fields = (
        "id",
        "type",
        "player",
        "side",
        "shot_type",
        "court_zone",
        "frame_start",
        "frame_end",
        "time_start_seconds",
        "time_end_seconds",
        "source",
        "notes",
    )
    for source, output in zip(source_events, output_events, strict=True):
        for field in preserved_fields:
            if source.get(field, "") != output.get(field, ""):
                raise RuntimeError(f"Normalized event {source['id']} changed field {field}")


def run_a2(
    *,
    video_path: Path,
    manifest_path: Path,
    frame_timestamps_path: Path,
    annotation_path: Path,
    output_dir: Path,
    persistence_source: str,
    backup_paths: list[Path],
) -> dict[str, object]:
    """Run the reproducible A2 Stage 4 pipeline without closing its human gate."""
    manifest = ClipManifest.read(manifest_path)
    sidecar = FrameTimestampSidecar.read(frame_timestamps_path)
    validate_sidecar_against_manifest(sidecar, manifest)
    if manifest.clip_id != CLIP_ID or manifest.frames_total != 527:
        raise RuntimeError("This runner requires the canonical 527-frame nivel_a2_01 clip")
    if (manifest.canonical_width, manifest.canonical_height) != (2746, 1536):
        raise RuntimeError("A2 manifest does not declare canonical 2746x1536 orientation")
    if manifest.timing_mode != "variable_frame_rate":
        raise RuntimeError("A2 manifest must declare variable_frame_rate")
    if sha256_file(video_path) != manifest.source_sha256:
        raise RuntimeError("Canonical source video SHA-256 does not match the manifest")

    annotation = load_annotation(annotation_path)
    if annotation.get("video_sha256") != manifest.source_sha256:
        raise RuntimeError("Annotation video_sha256 does not match the canonical video")
    output_dir.mkdir(parents=True, exist_ok=True)
    events_path = output_dir / "events.json"
    overlay_path = output_dir / "events_overlay.mp4"
    timeline_path = output_dir / "events_timeline.png"
    contact_sheet_path = output_dir / "events_contact_sheet.png"
    report_path = output_dir / "events_report.json"

    normalized = run_stage_4(
        annotation_path,
        events_path,
        frame_timestamps_path=frame_timestamps_path,
        clip_id=CLIP_ID,
    )
    _validate_normalized_events(annotation, normalized)
    events = normalized["events"]
    if len(events) != 9:
        raise RuntimeError(f"Expected 9 human events, found {len(events)}")
    timestamps = [frame.timestamp_seconds for frame in sidecar.frames]
    overlay = render_events_overlay(
        video_path,
        events_path,
        overlay_path,
        manifest=manifest,
        timestamps=timestamps,
    )
    overlay_timestamps = probe_frame_timestamps(overlay_path)
    if len(overlay_timestamps) != manifest.frames_total:
        raise RuntimeError("Generated overlay does not preserve all 527 frame timestamps")
    interval_values = timestamp_intervals(overlay_timestamps)
    distinct_intervals = sorted({round(value, 6) for value in interval_values})
    if len(distinct_intervals) < 2:
        raise RuntimeError("Generated overlay is not VFR")
    endpoints = _decode_overlay_endpoints(overlay_path)
    if endpoints["decoded_frames"] != manifest.frames_total:
        raise RuntimeError("Generated overlay decode count is not 527")
    if not endpoints["first_frame_readable"] or not endpoints["last_frame_readable"]:
        raise RuntimeError("Generated overlay endpoints are not readable")

    timeline = render_events_timeline(events_path, timeline_path)
    contact_sheet = render_events_contact_sheet(
        video_path,
        manifest,
        timestamps,
        events_path,
        contact_sheet_path,
    )
    for image_path in (timeline_path, contact_sheet_path):
        image = cv2.imread(str(image_path))
        if image is None or image.size == 0:
            raise RuntimeError(f"Generated review image is not readable: {image_path}")

    type_counts = Counter(str(event["type"]) for event in events)
    player_counts = Counter(str(event["player"]) for event in events)
    side_counts = Counter(str(event["side"]) for event in events)
    point_events = sum(event["frame_start"] == event["frame_end"] for event in events)
    audit = [
        {
            "id": event["id"],
            "type": event["type"],
            "player": event["player"],
            "side": event["side"],
            "frame_start": event["frame_start"],
            "frame_end": event["frame_end"],
            "frame_count": event["frame_end"] - event["frame_start"] + 1,
            "time_start_seconds": event["time_start_seconds"],
            "time_end_seconds": event["time_end_seconds"],
            "validation": "PASS",
        }
        for event in events
    ]
    report: dict[str, object] = {
        "schema_version": "1.0",
        "status": "IMPLEMENTED_PENDING_HUMAN_VISUAL_GATE",
        "clip_id": CLIP_ID,
        "persistence_source": persistence_source,
        "annotation_path": str(annotation_path),
        "annotation_sha256": sha256_file(annotation_path),
        "annotation_backups": [
            {"path": str(path), "sha256": sha256_file(path)} for path in backup_paths
        ],
        "video_sha256": manifest.source_sha256,
        "frame_count": manifest.frames_total,
        "first_frame_id": 0,
        "last_frame_id": manifest.frames_total - 1,
        "width": manifest.canonical_width,
        "height": manifest.canonical_height,
        "timing_mode": sidecar.timing_mode,
        "event_count": len(events),
        "type_counts": dict(type_counts),
        "player_counts": dict(player_counts),
        "side_counts": dict(side_counts),
        "point_events": point_events,
        "multiframe_events": len(events) - point_events,
        "events": audit,
        "outputs": {
            "events": str(events_path),
            "overlay": str(overlay_path),
            "timeline": str(timeline_path),
            "contact_sheet": str(contact_sheet_path),
        },
        "overlay_validation": {
            **overlay,
            **endpoints,
            "timing_mode": "variable_frame_rate",
            "distinct_frame_intervals_seconds": distinct_intervals,
            "last_timestamp_seconds": overlay_timestamps[-1],
        },
        "timeline_validation": timeline,
        "contact_sheet_validation": contact_sheet,
        "validations": {
            "annotation_matches_frame_timestamps": True,
            "normalized_events_lossless": True,
            "event_ids_unique": len({event["id"] for event in events}) == len(events),
            "events_chronological": events
            == sorted(events, key=lambda event: (event["frame_start"], event["frame_end"])),
            "overlay_canonical": True,
            "overlay_vfr": True,
            "overlay_last_frame_preserved": True,
            "timeline_readable": True,
            "contact_sheet_readable": True,
        },
        "limitations": [
            "Event semantics and frame ranges are human annotations, not automatic detections.",
            "The generated visual material still requires the human Stage 4 gate.",
            "Stage 5 has not started.",
        ],
    }
    if not all(report["validations"].values()):  # type: ignore[union-attr]
        raise RuntimeError("One or more Stage 4 report validations failed")
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, default=CLIP_DIR / "source.mp4")
    parser.add_argument("--manifest", type=Path, default=CLIP_DIR / "clip_manifest.json")
    parser.add_argument("--frame-timestamps", type=Path, default=CLIP_DIR / "frame_timestamps.json")
    parser.add_argument("--annotation", type=Path, default=CLIP_DIR / "manual_annotation.json")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument(
        "--persistence-source",
        choices=("final", "draft", "endpoint", "screenshot_backup"),
        default="final",
    )
    parser.add_argument("--backup", type=Path, action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_a2(
        video_path=args.video,
        manifest_path=args.manifest,
        frame_timestamps_path=args.frame_timestamps,
        annotation_path=args.annotation,
        output_dir=args.output_dir,
        persistence_source=args.persistence_source,
        backup_paths=args.backup,
    )
    print(f"Stage 4 A2 generated {report['event_count']} events with status {report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
