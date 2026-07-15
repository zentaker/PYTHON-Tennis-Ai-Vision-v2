"""Portable per-frame timestamp sidecars for VFR video clips."""

from __future__ import annotations

import json
import math
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.project.clip_manifest import ClipManifest


class FrameTimestampError(ValueError):
    """Raised when timestamp metadata is missing or internally inconsistent."""


@dataclass(frozen=True)
class FrameTimestamp:
    """Presentation timestamp and displayed duration for one decoded frame."""

    frame_id: int
    timestamp_seconds: float
    duration_seconds: float

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> FrameTimestamp:
        expected = {"frame_id", "timestamp_seconds", "duration_seconds"}
        if set(payload) != expected:
            raise FrameTimestampError("timestamp record fields do not match the schema")
        return cls(
            frame_id=payload["frame_id"],
            timestamp_seconds=payload["timestamp_seconds"],
            duration_seconds=payload["duration_seconds"],
        )


@dataclass(frozen=True)
class FrameTimestampSidecar:
    """Validated VFR timeline tied to a manifest clip."""

    schema_version: str
    clip_id: str
    video_path: str
    timing_mode: str
    timestamp_source: str
    frame_count: int
    frames: tuple[FrameTimestamp, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise FrameTimestampError("unsupported timestamp schema_version")
        if not self.clip_id or not isinstance(self.clip_id, str):
            raise FrameTimestampError("clip_id must be a non-empty string")
        if self.timing_mode not in {"constant_frame_rate", "variable_frame_rate"}:
            raise FrameTimestampError("invalid timing_mode")
        if self.frame_count != len(self.frames):
            raise FrameTimestampError("frame_count does not match the frame records")
        previous = -1.0
        for index, frame in enumerate(self.frames):
            if frame.frame_id != index:
                raise FrameTimestampError(f"expected frame_id {index}, found {frame.frame_id}")
            if (
                isinstance(frame.timestamp_seconds, bool)
                or not isinstance(frame.timestamp_seconds, (int, float))
                or not math.isfinite(frame.timestamp_seconds)
                or frame.timestamp_seconds < 0
            ):
                raise FrameTimestampError(f"invalid timestamp at frame {index}")
            if index and frame.timestamp_seconds <= previous:
                raise FrameTimestampError("timestamps must be strictly increasing")
            if (
                isinstance(frame.duration_seconds, bool)
                or not isinstance(frame.duration_seconds, (int, float))
                or not math.isfinite(frame.duration_seconds)
                or frame.duration_seconds <= 0
            ):
                raise FrameTimestampError(f"invalid duration at frame {index}")
            previous = float(frame.timestamp_seconds)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "clip_id": self.clip_id,
            "video_path": self.video_path,
            "timing_mode": self.timing_mode,
            "timestamp_source": self.timestamp_source,
            "frame_count": self.frame_count,
            "frames": [asdict(frame) for frame in self.frames],
        }

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def read(cls, path: Path) -> FrameTimestampSidecar:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FrameTimestampError(f"could not read timestamp sidecar: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise FrameTimestampError("timestamp sidecar root must be an object")
        expected = {
            "schema_version",
            "clip_id",
            "video_path",
            "timing_mode",
            "timestamp_source",
            "frame_count",
            "frames",
        }
        if set(payload) != expected:
            raise FrameTimestampError("timestamp sidecar fields do not match the schema")
        raw_frames = payload["frames"]
        if not isinstance(raw_frames, list):
            raise FrameTimestampError("frames must be a JSON array")
        return cls(
            schema_version=payload["schema_version"],
            clip_id=payload["clip_id"],
            video_path=payload["video_path"],
            timing_mode=payload["timing_mode"],
            timestamp_source=payload["timestamp_source"],
            frame_count=payload["frame_count"],
            frames=tuple(FrameTimestamp.from_dict(frame) for frame in raw_frames),
        )


def _positive_float(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise FrameTimestampError(f"invalid {label}") from exc
    if not math.isfinite(number) or number <= 0:
        raise FrameTimestampError(f"invalid {label}")
    return number


def build_frame_timestamp_sidecar(
    video_path: Path,
    manifest: ClipManifest,
    *,
    ffprobe_binary: str = "ffprobe",
) -> FrameTimestampSidecar:
    """Probe exact frame PTS/durations and validate them against the manifest."""
    command = [
        ffprobe_binary,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "frame=best_effort_timestamp_time,duration_time",
        "-of",
        "json",
        str(video_path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        payload = json.loads(result.stdout)
    except FileNotFoundError as exc:
        raise FrameTimestampError(f"ffprobe not found: {ffprobe_binary}") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or "unknown ffprobe error"
        raise FrameTimestampError(f"ffprobe failed: {detail}") from exc
    except json.JSONDecodeError as exc:
        raise FrameTimestampError("ffprobe returned invalid JSON") from exc

    raw_frames = payload.get("frames") if isinstance(payload, Mapping) else None
    if not isinstance(raw_frames, list):
        raise FrameTimestampError("ffprobe did not return a frame array")
    if len(raw_frames) != manifest.frames_total:
        raise FrameTimestampError(
            f"manifest expects {manifest.frames_total} frames; ffprobe found {len(raw_frames)}"
        )

    raw_timestamps = [
        float(frame["best_effort_timestamp_time"])
        for frame in raw_frames
        if isinstance(frame, Mapping) and frame.get("best_effort_timestamp_time") != "N/A"
    ]
    if len(raw_timestamps) != len(raw_frames):
        raise FrameTimestampError("one or more frames have no presentation timestamp")
    origin = raw_timestamps[0]
    timestamps = [timestamp - origin for timestamp in raw_timestamps]

    records: list[FrameTimestamp] = []
    for index, (raw, timestamp) in enumerate(zip(raw_frames, timestamps, strict=True)):
        if not isinstance(raw, Mapping) or raw.get("duration_time") in {None, "N/A"}:
            raise FrameTimestampError(f"frame {index} has no duration_time")
        records.append(
            FrameTimestamp(
                frame_id=index,
                timestamp_seconds=round(timestamp, 9),
                duration_seconds=round(_positive_float(raw["duration_time"], "duration"), 9),
            )
        )

    sidecar = FrameTimestampSidecar(
        schema_version="1.0",
        clip_id=manifest.clip_id,
        video_path=f"data/clips/{manifest.clip_id}/{manifest.source_filename}",
        timing_mode=manifest.timing_mode,
        timestamp_source="ffprobe.best_effort_timestamp_time+duration_time",
        frame_count=len(records),
        frames=tuple(records),
    )
    final_end = records[-1].timestamp_seconds + records[-1].duration_seconds
    if abs(final_end - manifest.duration_seconds) > 0.002:
        raise FrameTimestampError(
            f"timeline ends at {final_end:.6f}s; manifest duration is "
            f"{manifest.duration_seconds:.6f}s"
        )
    return sidecar


def validate_sidecar_against_manifest(
    sidecar: FrameTimestampSidecar, manifest: ClipManifest
) -> None:
    """Ensure a loaded sidecar belongs to the exact manifest clip contract."""
    if sidecar.clip_id != manifest.clip_id:
        raise FrameTimestampError("sidecar clip_id does not match manifest")
    if sidecar.frame_count != manifest.frames_total:
        raise FrameTimestampError("sidecar frame_count does not match manifest")
    if sidecar.timing_mode != manifest.timing_mode:
        raise FrameTimestampError("sidecar timing_mode does not match manifest")


def timestamp_values(frames: Sequence[FrameTimestamp]) -> list[float]:
    """Return timestamps as a simple sequence for canonical frame readers."""
    return [float(frame.timestamp_seconds) for frame in frames]
