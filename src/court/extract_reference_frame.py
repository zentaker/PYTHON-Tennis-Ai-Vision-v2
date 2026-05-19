"""Extract a reference frame from a local video clip."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2


def extract_reference_frame(clip_path: Path, output_path: Path, frame_index: int = 0) -> tuple[int, int, int]:
    """Extract one frame from a video and write it as an image.

    Returns the OpenCV frame shape as ``(height, width, channels)``.
    """
    if frame_index < 0:
        raise ValueError("frame_index must be >= 0")
    if not clip_path.exists():
        raise FileNotFoundError(f"Clip not found: {clip_path}")

    capture = cv2.VideoCapture(str(clip_path))
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"Could not open clip: {clip_path}")

    if frame_index:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)

    ok, frame = capture.read()
    capture.release()
    if not ok or frame is None:
        raise RuntimeError(f"Could not read frame {frame_index} from {clip_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), frame):
        raise RuntimeError(f"Could not write output image: {output_path}")

    return tuple(int(value) for value in frame.shape)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clip", type=Path, default=Path("data/reference_clip/madrid_R1.mov"))
    parser.add_argument("--output", type=Path, default=Path("data/reference_clip/reference_frame.png"))
    parser.add_argument("--frame", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    shape = extract_reference_frame(args.clip, args.output, args.frame)
    print(f"Extracted frame {args.frame} to {args.output} with shape={shape}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
