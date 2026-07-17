"""Stage P1 command line runtime with canonical video and manifest contracts."""

from __future__ import annotations

import argparse
import csv
import json
import tempfile
from pathlib import Path

import cv2
import numpy as np

from src.project.clip_manifest import ClipManifest
from src.video.canonical_frames import CanonicalFrameError, iter_canonical_frames

from .backends.mock_backend import MockBackend
from .backends.openmmlab_backend import OpenMMLabBackend
from .court_projection import CourtProjector
from .model_bundle import load_model_bundle
from .outputs import write_artifact_manifest, write_perception_outputs
from .pipeline import PerceptionPipeline
from .render import write_contact_sheet, write_pose_overlay
from .schemas import FrameInput


DEFAULT_MANIFEST = Path("data/clips/nivel_a2_01/clip_manifest.json")
DEFAULT_HOMOGRAPHY = Path("data/clips/nivel_a2_01/homography.json")


def _parse_frames(value: str | None) -> list[int] | None:
    if value is None:
        return None
    try:
        frames = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--frames must be a comma-separated integer list") from exc
    if not frames:
        raise argparse.ArgumentTypeError("--frames cannot be empty")
    if len(set(frames)) != len(frames):
        raise argparse.ArgumentTypeError("--frames cannot contain duplicates")
    return frames


def _selected_frames(args: argparse.Namespace, total: int) -> list[int]:
    frames = _parse_frames(args.frames)
    if frames is not None and (args.start_frame is not None or args.end_frame is not None):
        raise ValueError("--frames cannot be combined with --start-frame/--end-frame")
    if frames is None:
        start = 0 if args.start_frame is None else args.start_frame
        end = 9 if args.end_frame is None else args.end_frame
        if start > end:
            raise ValueError("start frame must be <= end frame")
        frames = list(range(start, end + 1))
    invalid = [frame for frame in frames if frame < 0 or frame >= total]
    if invalid:
        raise ValueError(f"frame IDs outside 0-{total - 1}: {invalid}")
    return frames


def _load_events(path: Path | None) -> list[dict[str, object]]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    events = payload.get("events", payload) if isinstance(payload, dict) else payload
    return [item for item in events if isinstance(item, dict)]


def _load_trajectory(path: Path | None) -> dict[int, tuple[float, float]]:
    if path is None or not path.is_file():
        return {}
    result: dict[int, tuple[float, float]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            x_value = row.get("x_smooth") or row.get("x_raw")
            y_value = row.get("y_smooth") or row.get("y_raw")
            if not x_value or not y_value:
                continue
            try:
                result[int(row["frame_id"])] = (float(x_value), float(y_value))
            except (KeyError, ValueError):
                continue
    return result


def _synthetic_frames(frame_ids: list[int]) -> list[FrameInput]:
    image = np.zeros((1536, 2746, 3), dtype=np.uint8)
    return [
        FrameInput(frame_id, frame_id / 50.0, image, image.shape[1], image.shape[0])
        for frame_id in frame_ids
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clip-id", default="nivel_a2_01")
    parser.add_argument("--video", type=Path)
    parser.add_argument("--image", type=Path, help="single decoded image for a CPU runtime gate")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--homography", type=Path, default=DEFAULT_HOMOGRAPHY)
    parser.add_argument("--trajectory", type=Path)
    parser.add_argument("--events", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--backend", choices=["mock", "openmmlab"], default="mock")
    parser.add_argument("--device", choices=["cpu", "cuda", "auto"], default="cpu")
    parser.add_argument("--frames")
    parser.add_argument("--start-frame", type=int)
    parser.add_argument("--end-frame", type=int)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--model-bundle", type=Path)
    parser.add_argument("--models-dir", type=Path, default=Path("/models"))
    parser.add_argument("--config-root", type=Path, default=Path("."))
    parser.add_argument("--fail-on-missing-models", action="store_true")
    parser.add_argument("--foot-smoothing-window", type=int, default=1)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest_path = args.manifest or DEFAULT_MANIFEST
    manifest = ClipManifest.read(manifest_path)
    if args.clip_id != manifest.clip_id:
        raise ValueError(f"clip ID {args.clip_id} does not match manifest {manifest.clip_id}")
    selected = _selected_frames(args, manifest.frames_total)
    output_dir = args.output_dir or Path(tempfile.mkdtemp(prefix="player_perception_p1_"))
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = None
    if args.model_bundle:
        bundle = load_model_bundle(args.model_bundle)
    if args.validate_only:
        if args.backend != "openmmlab":
            raise ValueError("--validate-only is only meaningful with --backend openmmlab")
        OpenMMLabBackend(
            model_bundle=args.model_bundle,
            models_dir=args.models_dir,
            config_root=args.config_root,
            device=args.device,
            validate_only=True,
        )
        print(json.dumps({"status": "VALIDATE_ONLY_OK", "model_bundle": str(args.model_bundle)}))
        return 0
    if args.backend == "openmmlab" and args.model_bundle is None:
        raise ValueError("--model-bundle is required for --backend openmmlab")
    backend = (
        MockBackend()
        if args.backend == "mock"
        else OpenMMLabBackend(
            args.model_bundle,
            args.models_dir,
            args.config_root,
            device=args.device,
        )
    )
    projector = CourtProjector(args.homography)
    pipeline = PerceptionPipeline(backend, projector, args.foot_smoothing_window)
    selected_set = set(selected)
    frame_inputs: list[FrameInput] = []
    if args.video and args.image:
        raise ValueError("--video and --image cannot be combined")
    if args.image:
        image = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(f"image not found or unreadable: {args.image}")
        if selected != [0]:
            raise ValueError("--image runtime gate requires exactly --frames 0")
        frame_inputs = [FrameInput(0, 0.0, image, image.shape[1], image.shape[0])]
    elif args.video:
        if not args.video.is_file():
            raise FileNotFoundError(f"video not found: {args.video}")
        try:
            source = iter_canonical_frames(args.video, manifest)
            for canonical in source:
                if canonical.frame_id in selected_set:
                    frame_inputs.append(
                        FrameInput(
                            canonical.frame_id,
                            canonical.timestamp_seconds,
                            canonical.image_bgr,
                            canonical.image_bgr.shape[1],
                            canonical.image_bgr.shape[0],
                        )
                    )
        except CanonicalFrameError:
            raise
    else:
        frame_inputs = _synthetic_frames(selected)
    if [item.frame_id for item in frame_inputs] != selected:
        raise RuntimeError("decoded frame selection did not produce the requested IDs")
    report = pipeline.run(frame_inputs, clip_id=args.clip_id, device=args.device)
    events = _load_events(args.events)
    trajectory = _load_trajectory(args.trajectory)
    paths = write_perception_outputs(report, output_dir, events=events, trajectory=trajectory)
    if args.render:
        overlay = write_pose_overlay(
            frame_inputs, report.frames, output_dir / "player_pose_overlay.mp4"
        )
        contact_sheet = write_contact_sheet(
            frame_inputs, report.frames, output_dir / "contact_audit_contact_sheet.png"
        )
        paths.update({overlay.name: overlay, contact_sheet.name: contact_sheet})
    paths["artifact_manifest.json"] = write_artifact_manifest(paths.values(), output_dir)
    summary = {
        "status": "COMPLETED",
        "clip_id": args.clip_id,
        "backend": args.backend,
        "device": args.device,
        "frames": len(selected),
        "frame_ids": selected,
        "timestamps_present": all(frame.timestamp_seconds >= 0 for frame in frame_inputs),
        "output_dir": str(output_dir),
        "model_bundle_loaded": bundle is not None,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
