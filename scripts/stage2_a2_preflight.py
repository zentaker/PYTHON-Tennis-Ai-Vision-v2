"""Lightweight Stage 2 A2 preflight; never imports or executes WASB/PyTorch."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.project.clip_manifest import ClipManifest  # noqa: E402
from src.video.canonical_frames import (  # noqa: E402
    apply_canonical_transform,
    probe_frame_timestamps,
    timestamp_intervals,
)


def sha256_file(path: Path) -> str:
    """Hash a file without loading it completely into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_cuda_runtime() -> dict[str, object]:
    """Check the external CUDA driver without importing torch."""
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return {"available": False, "reason": "nvidia-smi not found"}
    result = subprocess.run(
        [executable, "--query-gpu=name", "--format=csv=noheader"],
        capture_output=True,
        text=True,
        check=False,
    )
    names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return {
        "available": result.returncode == 0 and bool(names),
        "gpus": names,
        "reason": result.stderr.strip() if result.returncode else "",
    }


def run_preflight(
    video_path: Path,
    manifest_path: Path,
    *,
    homography_path: Path | None = None,
    output_csv: Path | None = None,
    output_overlay: Path | None = None,
    checkpoint_path: Path | None = None,
    wasb_root: Path | None = None,
    require_runtime: bool = False,
) -> dict[str, Any]:
    """Validate Stage 2 inputs, VFR timing and canonical geometry without inference."""
    if not video_path.is_file():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    manifest = ClipManifest.read(manifest_path)
    resolved_homography = homography_path or manifest_path.parent / "homography.json"
    resolved_csv = output_csv or manifest_path.parent / "wasb_detections.csv"
    resolved_overlay = output_overlay or (
        PROJECT_ROOT / "outputs" / manifest.clip_id / "stage_2" / "wasb_detections_overlay.mp4"
    )

    if video_path.suffix.lower() != manifest.source_extension:
        raise ValueError("Video extension does not match manifest")
    actual_sha256 = sha256_file(video_path)
    if actual_sha256 != manifest.source_sha256:
        raise ValueError("Video SHA-256 does not match manifest")
    if not resolved_homography.is_file():
        raise FileNotFoundError(f"Homography not found: {resolved_homography}")
    homography = json.loads(resolved_homography.read_text(encoding="utf-8"))
    if homography.get("clip_id") != manifest.clip_id:
        raise ValueError("Homography clip_id does not match manifest")
    if homography.get("frame_dimensions") != {
        "width": manifest.canonical_width,
        "height": manifest.canonical_height,
    }:
        raise ValueError("Homography dimensions do not match canonical manifest dimensions")

    timestamps = probe_frame_timestamps(video_path)
    if len(timestamps) != manifest.frames_total:
        raise ValueError(
            f"Expected {manifest.frames_total} timestamps, found {len(timestamps)}"
        )
    intervals = timestamp_intervals(timestamps)
    interval_values = sorted({round(value, 6) for value in intervals})
    variable_timing_confirmed = len(interval_values) > 1
    if manifest.timing_mode == "variable_frame_rate" and not variable_timing_confirmed:
        raise ValueError("Manifest declares VFR but probed timestamps are uniform")

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"OpenCV could not open video: {video_path}")
    reported_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    ok, first_frame = capture.read()
    capture.release()
    if not ok or first_frame is None:
        raise RuntimeError("OpenCV could not decode the first frame")
    canonical_first_frame = apply_canonical_transform(first_frame, manifest)
    if reported_frames != manifest.frames_total:
        raise ValueError(
            f"OpenCV reports {reported_frames} frames; manifest expects {manifest.frames_total}"
        )

    if resolved_csv.suffix.lower() != ".csv":
        raise ValueError("Stage 2 CSV output must use .csv")
    if resolved_overlay.suffix.lower() != ".mp4":
        raise ValueError("Stage 2 overlay output must use .mp4")

    checkpoint_exists = bool(checkpoint_path and checkpoint_path.is_file())
    wasb_source_exists = bool(wasb_root and (wasb_root / "src").is_dir())
    media_tools = {
        "ffprobe": shutil.which("ffprobe") is not None,
        "ffmpeg": shutil.which("ffmpeg") is not None,
    }
    cuda = check_cuda_runtime() if require_runtime else {"checked": False}
    if require_runtime:
        if not checkpoint_exists:
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
        if not wasb_source_exists:
            raise FileNotFoundError(f"WASB source not found under: {wasb_root}")
        if not cuda.get("available"):
            raise RuntimeError(f"CUDA runtime unavailable: {cuda}")
        missing_media_tools = [name for name, available in media_tools.items() if not available]
        if missing_media_tools:
            raise RuntimeError(
                f"Required media tools unavailable: {', '.join(missing_media_tools)}"
            )

    return {
        "status": "LIGHTWEIGHT_PREFLIGHT_PASSED",
        "inference_executed": False,
        "video": str(video_path),
        "video_sha256": actual_sha256,
        "manifest": str(manifest_path),
        "clip_id": manifest.clip_id,
        "homography": str(resolved_homography),
        "frames_manifest": manifest.frames_total,
        "frames_opencv": reported_frames,
        "timestamps_count": len(timestamps),
        "timestamp_backend": "ffprobe" if shutil.which("ffprobe") else "opencv_embedded_ffmpeg",
        "timestamps_monotonic": True,
        "variable_timing_confirmed": variable_timing_confirmed,
        "timestamp_intervals_seconds": interval_values,
        "decoded_dimensions": [manifest.decoded_width, manifest.decoded_height],
        "canonical_dimensions": [
            int(canonical_first_frame.shape[1]),
            int(canonical_first_frame.shape[0]),
        ],
        "canonical_transform": manifest.canonical_transform,
        "output_csv": str(resolved_csv),
        "output_overlay": str(resolved_overlay),
        "checkpoint": {
            "path": str(checkpoint_path) if checkpoint_path else None,
            "exists": checkpoint_exists,
        },
        "wasb_root": {
            "path": str(wasb_root) if wasb_root else None,
            "source_exists": wasb_source_exists,
        },
        "media_tools": media_tools,
        "cuda": cuda,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--homography", type=Path)
    parser.add_argument("--output-csv", type=Path)
    parser.add_argument("--output-overlay", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--wasb-root", type=Path)
    parser.add_argument("--require-runtime", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_preflight(
        args.video,
        args.manifest,
        homography_path=args.homography,
        output_csv=args.output_csv,
        output_overlay=args.output_overlay,
        checkpoint_path=args.checkpoint,
        wasb_root=args.wasb_root,
        require_runtime=args.require_runtime,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
