"""Shared timestamp-driven VFR overlay encoding for canonical video frames."""

from __future__ import annotations

import json
import subprocess
import tempfile
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

import cv2

from src.video.canonical_frames import CanonicalFrame


def write_vfr_concat_file(
    image_paths: Sequence[Path],
    timestamps: Sequence[float],
    output_path: Path,
) -> None:
    """Write an ffconcat list with microsecond time bases for sub-40 ms intervals."""
    if len(image_paths) != len(timestamps) or not image_paths:
        raise ValueError("Image paths and timestamps must have the same non-zero length")
    lines = ["ffconcat version 1.0"]
    for index, image_path in enumerate(image_paths):
        escaped_path = str(image_path.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped_path}'")
        lines.append("option framerate 1000000")
        if index + 1 < len(timestamps):
            duration = float(timestamps[index + 1] - timestamps[index])
            if duration <= 0:
                raise ValueError("Overlay timestamps must be strictly increasing")
            lines.append(f"duration {duration:.9f}")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def probe_overlay(path: Path, *, ffprobe_binary: str = "ffprobe") -> dict[str, float | int]:
    """Read encoded dimensions, decoded frame count and duration without visual review."""
    command = [
        ffprobe_binary,
        "-v",
        "error",
        "-count_frames",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,nb_read_frames,duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"ffprobe not found: {ffprobe_binary}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("ffprobe failed to inspect the VFR overlay") from exc
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    if len(streams) != 1:
        raise RuntimeError("Encoded overlay does not contain exactly one video stream")
    stream = streams[0]
    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "frames": int(stream["nb_read_frames"]),
        "duration_seconds": float(stream["duration"]),
    }


def encode_vfr_png_sequence(
    image_paths: Sequence[Path],
    timestamps: Sequence[float],
    output_path: Path,
    *,
    expected_frames: int,
    expected_width: int,
    expected_height: int,
    ffmpeg_binary: str = "ffmpeg",
    ffprobe_binary: str = "ffprobe",
) -> dict[str, float | int]:
    """Encode canonical PNGs with original presentation timestamps and verify output."""
    if len(image_paths) != expected_frames:
        raise ValueError(f"Expected {expected_frames} overlay images, found {len(image_paths)}")
    concat_path = image_paths[0].parent / "frames.ffconcat"
    write_vfr_concat_file(image_paths, timestamps, concat_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_binary,
        "-nostdin",
        "-y",
        "-v",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
        "-fps_mode",
        "vfr",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"ffmpeg not found: {ffmpeg_binary}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("ffmpeg failed to encode the VFR overlay") from exc

    metadata = probe_overlay(output_path, ffprobe_binary=ffprobe_binary)
    if metadata["frames"] != expected_frames:
        raise RuntimeError(
            f"Overlay frame count changed: expected {expected_frames}, got {metadata['frames']}"
        )
    if (metadata["width"], metadata["height"]) != (expected_width, expected_height):
        raise RuntimeError(
            f"Overlay has unexpected dimensions: {metadata['width']}x{metadata['height']}"
        )
    return metadata


def render_canonical_vfr_overlay(
    frames: Iterable[CanonicalFrame],
    output_path: Path,
    draw_frame: Callable[[CanonicalFrame], Any],
    *,
    expected_frames: int,
    expected_width: int,
    expected_height: int,
    ffmpeg_binary: str = "ffmpeg",
    ffprobe_binary: str = "ffprobe",
) -> dict[str, float | int]:
    """Render canonical frames to temporary PNGs and encode a verified VFR MP4."""
    with tempfile.TemporaryDirectory(prefix="canonical_overlay_") as directory:
        temp_path = Path(directory)
        image_paths: list[Path] = []
        timestamps: list[float] = []
        for expected_frame_id, record in enumerate(frames):
            if record.frame_id != expected_frame_id:
                raise ValueError("Canonical overlay frame IDs are not consecutive")
            image = draw_frame(record)
            height, width = image.shape[:2]
            if (width, height) != (expected_width, expected_height):
                raise ValueError(f"Overlay frame has unexpected dimensions: {width}x{height}")
            image_path = temp_path / f"frame_{record.frame_id:06d}.png"
            if not cv2.imwrite(str(image_path), image):
                raise RuntimeError(f"Could not write temporary overlay frame: {image_path}")
            image_paths.append(image_path)
            timestamps.append(float(record.timestamp_seconds))
        return encode_vfr_png_sequence(
            image_paths,
            timestamps,
            output_path,
            expected_frames=expected_frames,
            expected_width=expected_width,
            expected_height=expected_height,
            ffmpeg_binary=ffmpeg_binary,
            ffprobe_binary=ffprobe_binary,
        )
