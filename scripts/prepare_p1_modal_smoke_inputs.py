#!/usr/bin/env python3
"""Extract and verify the approved ten canonical P1 smoke frames locally."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import cv2

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.project.clip_manifest import ClipManifest
from src.video.canonical_frames import iter_canonical_frames


DEFAULT_SELECTION = Path("config/player_perception/p1_smoke_frames.json")
DEFAULT_VIDEO = Path("data/clips/nivel_a2_01/source.mp4")
DEFAULT_MANIFEST = Path("data/clips/nivel_a2_01/clip_manifest.json")
DEFAULT_EVENTS = Path("outputs/nivel_a2_01/stage_4/events.json")
DEFAULT_OUTPUT = Path(".modal_smoke/nivel_a2_01")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_selection(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    frame_ids = payload.get("frame_ids")
    if not isinstance(frame_ids, list) or len(frame_ids) != 10:
        raise ValueError("p1 smoke selection must contain exactly ten frame IDs")
    if sorted(frame_ids) != frame_ids or len(set(frame_ids)) != 10:
        raise ValueError("p1 smoke frame IDs must be unique and sorted")
    return payload


def prepare_package(
    video: Path = DEFAULT_VIDEO,
    manifest_path: Path = DEFAULT_MANIFEST,
    selection_path: Path = DEFAULT_SELECTION,
    events_path: Path = DEFAULT_EVENTS,
    output_root: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    """Extract exactly ten frames; this function never invokes inference or network code."""
    manifest = ClipManifest.read(manifest_path)
    selection = _load_selection(selection_path)
    frame_ids = [int(value) for value in selection["frame_ids"]]
    if any(frame_id < 0 or frame_id >= manifest.frames_total for frame_id in frame_ids):
        raise ValueError("selected frame is outside the clip manifest")
    if not video.is_file():
        raise FileNotFoundError(video)
    events = json.loads(events_path.read_text(encoding="utf-8"))["events"] if events_path.is_file() else []
    event_map: dict[int, list[str]] = {frame_id: [] for frame_id in frame_ids}
    for event in events:
        start = int(event.get("frame_start", 0))
        end = int(event.get("frame_end", start))
        for frame_id in frame_ids:
            if start <= frame_id <= end:
                event_map[frame_id].append(str(event["id"]))

    frames_dir = output_root / "inputs" / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    wanted = set(frame_ids)
    records: list[dict[str, Any]] = []
    for canonical in iter_canonical_frames(video, manifest):
        if canonical.frame_id not in wanted:
            continue
        destination = frames_dir / f"frame_{canonical.frame_id:06d}.jpg"
        if not cv2.imwrite(str(destination), canonical.image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95]):
            raise RuntimeError(f"could not write {destination}")
        records.append(
            {
                "frame_id": canonical.frame_id,
                "timestamp_seconds": canonical.timestamp_seconds,
                "width": int(canonical.image_bgr.shape[1]),
                "height": int(canonical.image_bgr.shape[0]),
                "path": str(destination.relative_to(output_root)),
                "sha256": _sha256(destination),
                "event_ids": event_map[canonical.frame_id],
            }
        )
    if [record["frame_id"] for record in records] != frame_ids:
        raise ValueError("decoded package does not contain the ten requested frames")
    package = {
        "schema_version": "1.0",
        "clip_id": manifest.clip_id,
        "source_video_sha256": manifest.source_sha256,
        "frame_count": 10,
        "frame_ids": frame_ids,
        "frames": records,
        "selection": selection,
    }
    package_path = output_root / "inputs" / "p1_smoke_manifest.json"
    package_path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    return package


def verify_package(package_path: Path) -> dict[str, Any]:
    package = json.loads(package_path.read_text(encoding="utf-8"))
    if package.get("frame_count") != 10 or len(package.get("frames", [])) != 10:
        raise ValueError("smoke package must contain exactly ten frames")
    root = package_path.parent.parent
    for record in package["frames"]:
        path = root / record["path"]
        if not path.is_file() or _sha256(path) != record["sha256"]:
            raise ValueError(f"frame checksum mismatch: {path}")
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    package = prepare_package(args.video, args.manifest, args.selection, args.events, args.output_root)
    verify_package(args.output_root / "inputs" / "p1_smoke_manifest.json")
    print(json.dumps({"status": "PREPARED", "frame_ids": package["frame_ids"], "output": str(args.output_root)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
