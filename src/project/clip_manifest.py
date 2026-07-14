"""Validated manifest for a canonical Tennis Vision AI clip."""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Mapping


ALLOWED_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov"})
ALLOWED_CAMERA_MODES = frozenset({"fixed", "moving", "mixed", "unknown"})
ALLOWED_CANONICAL_TRANSFORMS = frozenset({"none", "rotate_90_ccw"})
ALLOWED_TIMING_MODES = frozenset({"constant_frame_rate", "variable_frame_rate"})
ALLOWED_STATUSES = frozenset(
    {
        "candidate",
        "selected",
        "rejected",
        "stage_1_prepared",
        "stage_1_awaiting_human_gate",
        "stage_1_closed",
        "stage_2_prepared_external",
        "archived",
    }
)
CLIP_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class ClipManifestError(ValueError):
    """Raised when a clip manifest is incomplete or internally inconsistent."""


def _positive_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool):
        raise ClipManifestError(f"{field_name} must be a positive number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ClipManifestError(f"{field_name} must be a positive number") from exc
    if not math.isfinite(number) or number <= 0:
        raise ClipManifestError(f"{field_name} must be a positive number")
    return number


def _positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ClipManifestError(f"{field_name} must be a positive integer")
    return value


@dataclass(frozen=True)
class ClipManifest:
    """Portable metadata for one immutable canonical source video."""

    clip_id: str
    source_filename: str
    source_extension: str
    source_sha256: str
    fps: float
    frames_total: int
    duration_seconds: float
    resolution_width: int
    resolution_height: int
    codec: str
    camera_mode: str
    status: str
    container_rotation_degrees: int
    decoded_width: int
    decoded_height: int
    canonical_width: int
    canonical_height: int
    canonical_transform: str
    timing_mode: str
    notes: str

    def __post_init__(self) -> None:
        if not isinstance(self.clip_id, str) or not CLIP_ID_PATTERN.fullmatch(self.clip_id):
            raise ClipManifestError(
                "clip_id must use lowercase letters, numbers, underscores, or hyphens"
            )
        if not isinstance(self.source_filename, str) or not self.source_filename:
            raise ClipManifestError("source_filename must be a non-empty basename")
        if Path(self.source_filename).name != self.source_filename:
            raise ClipManifestError("source_filename must not contain directories")
        if self.source_extension not in ALLOWED_VIDEO_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_VIDEO_EXTENSIONS))
            raise ClipManifestError(f"source_extension must be one of: {allowed}")
        if Path(self.source_filename).suffix.lower() != self.source_extension:
            raise ClipManifestError("source_filename suffix must match source_extension")
        if (
            not isinstance(self.source_sha256, str)
            or len(self.source_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.source_sha256)
        ):
            raise ClipManifestError("source_sha256 must be 64 lowercase hexadecimal characters")

        _positive_number(self.fps, "fps")
        _positive_integer(self.frames_total, "frames_total")
        _positive_number(self.duration_seconds, "duration_seconds")
        _positive_integer(self.resolution_width, "resolution_width")
        _positive_integer(self.resolution_height, "resolution_height")

        if not isinstance(self.codec, str) or not self.codec.strip():
            raise ClipManifestError("codec must be a non-empty string")
        if self.camera_mode not in ALLOWED_CAMERA_MODES:
            allowed = ", ".join(sorted(ALLOWED_CAMERA_MODES))
            raise ClipManifestError(f"camera_mode must be one of: {allowed}")
        if self.status not in ALLOWED_STATUSES:
            allowed = ", ".join(sorted(ALLOWED_STATUSES))
            raise ClipManifestError(f"status must be one of: {allowed}")
        if self.container_rotation_degrees not in {0, 90, 180, 270}:
            raise ClipManifestError("container_rotation_degrees must be 0, 90, 180, or 270")
        _positive_integer(self.decoded_width, "decoded_width")
        _positive_integer(self.decoded_height, "decoded_height")
        _positive_integer(self.canonical_width, "canonical_width")
        _positive_integer(self.canonical_height, "canonical_height")
        if self.canonical_transform not in ALLOWED_CANONICAL_TRANSFORMS:
            allowed = ", ".join(sorted(ALLOWED_CANONICAL_TRANSFORMS))
            raise ClipManifestError(f"canonical_transform must be one of: {allowed}")
        if self.timing_mode not in ALLOWED_TIMING_MODES:
            allowed = ", ".join(sorted(ALLOWED_TIMING_MODES))
            raise ClipManifestError(f"timing_mode must be one of: {allowed}")
        if self.canonical_transform == "none":
            expected_dimensions = (self.decoded_width, self.decoded_height)
        else:
            expected_dimensions = (self.decoded_height, self.decoded_width)
        if (self.canonical_width, self.canonical_height) != expected_dimensions:
            raise ClipManifestError(
                "canonical dimensions are inconsistent with decoded dimensions and transform"
            )
        if (self.resolution_width, self.resolution_height) != (
            self.canonical_width,
            self.canonical_height,
        ):
            raise ClipManifestError("resolution dimensions must match canonical dimensions")
        if not isinstance(self.notes, str):
            raise ClipManifestError("notes must be a string")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable manifest."""
        return asdict(self)

    def write(self, path: Path) -> None:
        """Persist the manifest as stable UTF-8 JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ClipManifest:
        """Validate a decoded JSON object and build a manifest."""
        if not isinstance(payload, Mapping):
            raise ClipManifestError("manifest root must be a JSON object")
        expected = {field.name for field in fields(cls)}
        missing = sorted(expected.difference(payload))
        unexpected = sorted(set(payload).difference(expected))
        if missing:
            raise ClipManifestError(f"manifest missing fields: {', '.join(missing)}")
        if unexpected:
            raise ClipManifestError(f"manifest has unexpected fields: {', '.join(unexpected)}")
        return cls(**{name: payload[name] for name in expected})

    @classmethod
    def read(cls, path: Path) -> ClipManifest:
        """Load and validate a manifest from disk."""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ClipManifestError(f"manifest is not valid JSON: {exc}") from exc
        return cls.from_dict(payload)
