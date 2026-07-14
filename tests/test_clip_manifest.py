from __future__ import annotations

from pathlib import Path

import pytest

from src.project.clip_manifest import ClipManifest, ClipManifestError


VALID_SHA256 = "a" * 64


def valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "clip_id": "nivel_a2_01",
        "source_filename": "source.mp4",
        "source_extension": ".mp4",
        "source_sha256": VALID_SHA256,
        "fps": 50.0,
        "frames_total": 469,
        "duration_seconds": 9.38,
        "resolution_width": 2746,
        "resolution_height": 1536,
        "codec": "hevc",
        "camera_mode": "fixed",
        "status": "stage_1_prepared",
        "container_rotation_degrees": 270,
        "decoded_width": 1536,
        "decoded_height": 2746,
        "canonical_width": 2746,
        "canonical_height": 1536,
        "canonical_transform": "rotate_90_ccw",
        "timing_mode": "variable_frame_rate",
        "notes": "Synthetic manifest fixture",
    }
    payload.update(overrides)
    return payload


def test_valid_mp4_manifest() -> None:
    manifest = ClipManifest.from_dict(valid_payload())

    assert manifest.clip_id == "nivel_a2_01"
    assert manifest.source_extension == ".mp4"


def test_mov_extension_is_allowed() -> None:
    manifest = ClipManifest.from_dict(
        valid_payload(source_filename="source.mov", source_extension=".mov")
    )

    assert manifest.source_extension == ".mov"


def test_stage_1_awaiting_human_gate_status_is_allowed() -> None:
    manifest = ClipManifest.from_dict(valid_payload(status="stage_1_awaiting_human_gate"))

    assert manifest.status == "stage_1_awaiting_human_gate"


def test_stage_2_prepared_external_status_is_allowed() -> None:
    manifest = ClipManifest.from_dict(valid_payload(status="stage_2_prepared_external"))

    assert manifest.status == "stage_2_prepared_external"


def test_transform_dimensions_must_be_consistent() -> None:
    with pytest.raises(ClipManifestError, match="canonical dimensions"):
        ClipManifest.from_dict(valid_payload(canonical_width=1536, canonical_height=2746))


def test_unsupported_extension_is_rejected() -> None:
    with pytest.raises(ClipManifestError, match="source_extension"):
        ClipManifest.from_dict(
            valid_payload(source_filename="source.avi", source_extension=".avi")
        )


@pytest.mark.parametrize("fps", [0, -1, float("nan")])
def test_fps_must_be_positive(fps: float) -> None:
    with pytest.raises(ClipManifestError, match="fps"):
        ClipManifest.from_dict(valid_payload(fps=fps))


@pytest.mark.parametrize("frames_total", [0, -1, 1.5, True])
def test_frames_total_must_be_positive_integer(frames_total: object) -> None:
    with pytest.raises(ClipManifestError, match="frames_total"):
        ClipManifest.from_dict(valid_payload(frames_total=frames_total))


@pytest.mark.parametrize(
    ("field", "value"),
    [("resolution_width", 0), ("resolution_height", -1), ("resolution_width", 2.5)],
)
def test_resolution_must_use_positive_integers(field: str, value: object) -> None:
    with pytest.raises(ClipManifestError, match=field):
        ClipManifest.from_dict(valid_payload(**{field: value}))


def test_serialization_round_trip(tmp_path: Path) -> None:
    original = ClipManifest.from_dict(valid_payload())
    path = tmp_path / "clip_manifest.json"

    original.write(path)
    restored = ClipManifest.read(path)

    assert restored == original
    assert restored.to_dict() == valid_payload()
