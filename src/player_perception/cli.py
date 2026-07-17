"""Portable CLI; mock backend is the only backend executed during P1 preparation."""

from __future__ import annotations

import argparse
import csv
import json
import tempfile
from pathlib import Path

from .backends.mock_backend import MockBackend
from .backends.openmmlab_backend import OpenMMLabBackend
from .court_projection import CourtProjector
from .pipeline import PerceptionPipeline


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clip-id", default="nivel_a2_01")
    parser.add_argument("--video")
    parser.add_argument("--manifest")
    parser.add_argument("--homography", default="data/clips/nivel_a2_01/homography.json")
    parser.add_argument("--trajectory")
    parser.add_argument("--events")
    parser.add_argument("--output-dir")
    parser.add_argument("--backend", choices=["mock", "openmmlab"], default="mock")
    parser.add_argument("--device", choices=["cpu", "cuda", "auto"], default="cpu")
    parser.add_argument("--start-frame", type=int, default=0)
    parser.add_argument("--end-frame", type=int, default=9)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    if args.backend == "openmmlab":
        OpenMMLabBackend(config_path=None, device=args.device)
    backend = MockBackend() if args.backend == "mock" else OpenMMLabBackend(device=args.device)
    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else Path(tempfile.mkdtemp(prefix="player_perception_smoke_"))
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    report = PerceptionPipeline(backend, CourtProjector(Path(args.homography))).run(
        range(args.start_frame, args.end_frame + 1),
        clip_id=args.clip_id,
        device=args.device,
    )
    (output_dir / "perception_report.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
    tracks = []
    positions = []
    for frame in report.frames:
        for track in frame.tracks:
            tracks.append(
                {
                    "frame_id": frame.frame_id,
                    "track_id": track.track_id,
                    "identity": track.identity,
                    "x1": track.bbox.x1,
                    "y1": track.bbox.y1,
                    "x2": track.bbox.x2,
                    "y2": track.bbox.y2,
                    "confidence": track.confidence,
                }
            )
        for pos in frame.court_positions:
            positions.append(
                {
                    "frame_id": pos.frame_id,
                    "track_id": pos.track_id,
                    "X_m": pos.x_m,
                    "Y_m": pos.y_m,
                    "distance_to_near_baseline_m": pos.distance_to_near_baseline_m,
                    "distance_to_far_baseline_m": pos.distance_to_far_baseline_m,
                    "inside_court": pos.inside_court,
                    "behind_far_baseline": pos.behind_far_baseline,
                    "behind_near_baseline": pos.behind_near_baseline,
                }
            )
    for name, records in (("player_tracks.csv", tracks), ("player_court_positions.csv", positions)):
        with (output_dir / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=list(records[0]) if records else ["frame_id"]
            )
            writer.writeheader()
            writer.writerows(records)
    print(
        json.dumps(
            {"backend": args.backend, "frames": report.frame_count, "output_dir": str(output_dir)},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
