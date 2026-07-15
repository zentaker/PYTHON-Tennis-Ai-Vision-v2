"""Generate a validated frame_timestamps.json sidecar for a clip manifest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.project.clip_manifest import ClipManifest  # noqa: E402
from src.video.frame_timestamps import build_frame_timestamp_sidecar  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ffprobe", default="ffprobe")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = ClipManifest.read(args.manifest)
    sidecar = build_frame_timestamp_sidecar(
        args.video,
        manifest,
        ffprobe_binary=args.ffprobe,
    )
    sidecar.write(args.output)
    print(
        f"wrote {sidecar.frame_count} frames to {args.output} "
        f"({sidecar.frames[0].timestamp_seconds:.6f}s.."
        f"{sidecar.frames[-1].timestamp_seconds:.6f}s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
