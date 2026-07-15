from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from src.project.clip_manifest import ClipManifest
from src.video.frame_timestamps import (
    FrameTimestampError,
    FrameTimestampSidecar,
    build_frame_timestamp_sidecar,
    validate_sidecar_against_manifest,
)


def manifest(**overrides: object) -> ClipManifest:
    payload: dict[str, object] = {
        "clip_id": "nivel_a2_01",
        "source_filename": "source.mp4",
        "source_extension": ".mp4",
        "source_sha256": "a" * 64,
        "fps": 50.0,
        "frames_total": 3,
        "duration_seconds": 0.07,
        "resolution_width": 4,
        "resolution_height": 2,
        "codec": "hevc",
        "camera_mode": "fixed",
        "status": "stage_2_prepared_external",
        "container_rotation_degrees": 270,
        "decoded_width": 2,
        "decoded_height": 4,
        "canonical_width": 4,
        "canonical_height": 2,
        "canonical_transform": "rotate_90_ccw",
        "timing_mode": "variable_frame_rate",
        "notes": "test",
    }
    payload.update(overrides)
    return ClipManifest.from_dict(payload)


def ffprobe_result() -> subprocess.CompletedProcess[str]:
    payload = {
        "frames": [
            {"best_effort_timestamp_time": "2.000000", "duration_time": "0.020000"},
            {"best_effort_timestamp_time": "2.020000", "duration_time": "0.030000"},
            {"best_effort_timestamp_time": "2.050000", "duration_time": "0.020000"},
        ]
    }
    return subprocess.CompletedProcess([], 0, stdout=json.dumps(payload), stderr="")


def test_builds_normalized_vfr_sidecar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: ffprobe_result())

    sidecar = build_frame_timestamp_sidecar(Path("source.mp4"), manifest())

    assert sidecar.frame_count == 3
    assert [frame.frame_id for frame in sidecar.frames] == [0, 1, 2]
    assert [frame.timestamp_seconds for frame in sidecar.frames] == [0.0, 0.02, 0.05]
    assert [frame.duration_seconds for frame in sidecar.frames] == [0.02, 0.03, 0.02]


def test_sidecar_round_trip_and_manifest_validation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: ffprobe_result())
    path = tmp_path / "frame_timestamps.json"
    build_frame_timestamp_sidecar(Path("source.mp4"), manifest()).write(path)

    loaded = FrameTimestampSidecar.read(path)
    validate_sidecar_against_manifest(loaded, manifest())

    assert loaded.frames[-1].timestamp_seconds == 0.05


def test_rejects_wrong_frame_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: ffprobe_result())

    with pytest.raises(FrameTimestampError, match="expects 2 frames"):
        build_frame_timestamp_sidecar(Path("source.mp4"), manifest(frames_total=2))
