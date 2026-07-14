"""Decode video frames into the manifest-declared canonical coordinate space."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.project.clip_manifest import ClipManifest


class CanonicalFrameError(ValueError):
    """Raised when decoded frames or timestamps violate the clip contract."""


@dataclass(frozen=True)
class CanonicalFrame:
    """One decoded frame with its original logical identity and timestamp."""

    frame_id: int
    timestamp_seconds: float
    image_bgr: np.ndarray


def _normalize_timestamps(timestamps: Sequence[float]) -> list[float]:
    """Normalize a presentation timeline to frame zero while preserving every interval."""
    if not timestamps:
        return []
    first_timestamp = timestamps[0]
    normalized = [float(timestamp - first_timestamp) for timestamp in timestamps]
    validate_timestamps(normalized)
    return normalized


def probe_opencv_frame_timestamps(
    video_path: Path,
    capture_factory: Callable[[str], Any] = cv2.VideoCapture,
) -> list[float]:
    """Decode sequentially and read timestamps from OpenCV's embedded video backend."""
    capture = capture_factory(str(video_path))
    if not capture.isOpened():
        raise CanonicalFrameError(f"Could not open video for timestamp probing: {video_path}")
    timestamps: list[float] = []
    try:
        while True:
            ok, _frame = capture.read()
            if not ok:
                break
            timestamps.append(float(capture.get(cv2.CAP_PROP_POS_MSEC)) / 1000.0)
    finally:
        capture.release()
    return _normalize_timestamps(timestamps)


def probe_frame_timestamps(video_path: Path, ffprobe_binary: str = "ffprobe") -> list[float]:
    """Read per-frame timestamps via ffprobe or a decoding OpenCV fallback."""
    command = [
        ffprobe_binary,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "frame=best_effort_timestamp_time",
        "-of",
        "csv=p=0",
        str(video_path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        return probe_opencv_frame_timestamps(video_path)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or "unknown ffprobe error"
        raise CanonicalFrameError(f"Could not probe frame timestamps: {detail}") from exc

    timestamps: list[float] = []
    for line in result.stdout.splitlines():
        value = line.strip().split(",", maxsplit=1)[0]
        if not value or value == "N/A":
            continue
        timestamps.append(float(value))
    return _normalize_timestamps(timestamps)


def validate_timestamps(timestamps: Sequence[float], expected_count: int | None = None) -> None:
    """Require finite, strictly increasing timestamps and an optional exact count."""
    if expected_count is not None and len(timestamps) != expected_count:
        raise CanonicalFrameError(
            f"Expected {expected_count} timestamps, found {len(timestamps)}"
        )
    for index, timestamp in enumerate(timestamps):
        if not np.isfinite(timestamp) or timestamp < 0:
            raise CanonicalFrameError(f"Invalid timestamp at frame {index}: {timestamp}")
        if index and timestamp <= timestamps[index - 1]:
            raise CanonicalFrameError(
                f"Timestamps must increase: frame {index - 1}={timestamps[index - 1]}, "
                f"frame {index}={timestamp}"
            )


def timestamp_intervals(timestamps: Sequence[float]) -> list[float]:
    """Return consecutive timestamp differences."""
    validate_timestamps(timestamps)
    return [float(current - previous) for previous, current in zip(timestamps, timestamps[1:])]


def apply_canonical_transform(frame_bgr: np.ndarray, manifest: ClipManifest) -> np.ndarray:
    """Transform a decoded frame once, accepting an already-canonical frame unchanged."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        raise CanonicalFrameError(f"Expected a BGR image with 3 channels, got {frame_bgr.shape}")

    height, width = frame_bgr.shape[:2]
    canonical_shape = (manifest.canonical_height, manifest.canonical_width)
    decoded_shape = (manifest.decoded_height, manifest.decoded_width)
    if (height, width) == canonical_shape:
        canonical = frame_bgr
    elif (height, width) == decoded_shape:
        if manifest.canonical_transform == "rotate_90_ccw":
            canonical = cv2.rotate(frame_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
        elif manifest.canonical_transform == "none":
            canonical = frame_bgr
        else:
            raise CanonicalFrameError(
                f"Unsupported canonical transform: {manifest.canonical_transform}"
            )
    else:
        raise CanonicalFrameError(
            f"Unexpected decoded dimensions {width}x{height}; expected "
            f"{manifest.decoded_width}x{manifest.decoded_height} or canonical "
            f"{manifest.canonical_width}x{manifest.canonical_height}"
        )

    output_height, output_width = canonical.shape[:2]
    if (output_width, output_height) != (
        manifest.canonical_width,
        manifest.canonical_height,
    ):
        raise CanonicalFrameError(
            f"Canonical output is {output_width}x{output_height}, expected "
            f"{manifest.canonical_width}x{manifest.canonical_height}"
        )
    return canonical


def transform_point_to_canonical(
    x_pixel: float,
    y_pixel: float,
    manifest: ClipManifest,
) -> tuple[float, float]:
    """Map a point from the declared decoded space into canonical pixel coordinates."""
    if not (0 <= x_pixel < manifest.decoded_width and 0 <= y_pixel < manifest.decoded_height):
        raise CanonicalFrameError("Decoded point is outside manifest dimensions")
    if manifest.canonical_transform == "rotate_90_ccw":
        canonical_x = y_pixel
        canonical_y = manifest.decoded_width - 1 - x_pixel
    elif manifest.canonical_transform == "none":
        canonical_x, canonical_y = x_pixel, y_pixel
    else:
        raise CanonicalFrameError(f"Unsupported canonical transform: {manifest.canonical_transform}")
    if not (
        0 <= canonical_x < manifest.canonical_width
        and 0 <= canonical_y < manifest.canonical_height
    ):
        raise CanonicalFrameError("Transformed point is outside canonical dimensions")
    return float(canonical_x), float(canonical_y)


def iter_canonical_frames(
    video_path: Path,
    manifest: ClipManifest,
    *,
    timestamps: Sequence[float] | None = None,
    capture_factory: Callable[[str], Any] = cv2.VideoCapture,
) -> Iterator[CanonicalFrame]:
    """Yield one canonical output for every decoded frame, preserving IDs and VFR time."""
    resolved_timestamps = list(timestamps) if timestamps is not None else probe_frame_timestamps(video_path)
    validate_timestamps(resolved_timestamps, expected_count=manifest.frames_total)

    capture = capture_factory(str(video_path))
    if not capture.isOpened():
        raise CanonicalFrameError(f"Could not open video: {video_path}")

    decoded_count = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if decoded_count >= len(resolved_timestamps):
                raise CanonicalFrameError("Decoded more frames than probed timestamps")
            yield CanonicalFrame(
                frame_id=decoded_count,
                timestamp_seconds=float(resolved_timestamps[decoded_count]),
                image_bgr=apply_canonical_transform(frame, manifest),
            )
            decoded_count += 1
    finally:
        capture.release()

    if decoded_count != manifest.frames_total:
        raise CanonicalFrameError(
            f"Expected {manifest.frames_total} decoded frames, found {decoded_count}"
        )
