from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.project.clip_manifest import ClipManifest
from src.video.canonical_frames import (
    CanonicalFrameError,
    apply_canonical_transform,
    iter_canonical_frames,
    probe_opencv_frame_timestamps,
    timestamp_intervals,
    transform_point_to_canonical,
    validate_timestamps,
)


def manifest(**overrides: object) -> ClipManifest:
    payload: dict[str, object] = {
        "clip_id": "nivel_a2_01",
        "source_filename": "source.mp4",
        "source_extension": ".mp4",
        "source_sha256": "a" * 64,
        "fps": 50.0,
        "frames_total": 3,
        "duration_seconds": 0.06,
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


class FakeCapture:
    def __init__(self, _path: str, frames: list[np.ndarray]) -> None:
        self.frames = iter(frames)
        self.released = False

    def isOpened(self) -> bool:
        return True

    def read(self) -> tuple[bool, np.ndarray | None]:
        try:
            return True, next(self.frames)
        except StopIteration:
            return False, None

    def release(self) -> None:
        self.released = True


class TimestampCapture(FakeCapture):
    def __init__(self, path: str, frames: list[np.ndarray], timestamps_ms: list[float]) -> None:
        super().__init__(path, frames)
        self.timestamps = iter(timestamps_ms)
        self.current_timestamp = 0.0

    def read(self) -> tuple[bool, np.ndarray | None]:
        ok, frame = super().read()
        if ok:
            self.current_timestamp = next(self.timestamps)
        return ok, frame

    def get(self, _property: int) -> float:
        return self.current_timestamp


def decoded_frame(value: int = 1) -> np.ndarray:
    return np.full((4, 2, 3), value, dtype=np.uint8)


def test_rotates_decoded_frame_to_canonical_dimensions() -> None:
    result = apply_canonical_transform(decoded_frame(), manifest())

    assert result.shape == (2, 4, 3)


def test_already_canonical_frame_is_not_rotated_twice() -> None:
    frame = np.zeros((2, 4, 3), dtype=np.uint8)

    result = apply_canonical_transform(frame, manifest())

    assert result.shape == frame.shape
    assert np.shares_memory(result, frame)


def test_reader_preserves_frame_ids_count_and_variable_timestamps() -> None:
    frames = [decoded_frame(index) for index in range(3)]
    timestamps = [0.0, 1 / 60, 1 / 20]
    capture = FakeCapture("unused", frames)

    records = list(
        iter_canonical_frames(
            Path("clip.mp4"),
            manifest(),
            timestamps=timestamps,
            capture_factory=lambda _path: capture,
        )
    )

    assert [record.frame_id for record in records] == [0, 1, 2]
    assert [record.timestamp_seconds for record in records] == timestamps
    assert len(records) == len(frames)
    assert len({round(value, 6) for value in timestamp_intervals(timestamps)}) == 2
    assert capture.released is True


def test_timestamps_must_be_monotonic_but_not_uniform() -> None:
    validate_timestamps([0.0, 0.016, 0.050])

    with pytest.raises(CanonicalFrameError, match="increase"):
        validate_timestamps([0.0, 0.016, 0.015])


def test_opencv_timestamp_fallback_normalizes_start_and_preserves_vfr() -> None:
    capture = TimestampCapture(
        "unused",
        [decoded_frame(), decoded_frame(), decoded_frame()],
        [-11.666667, 21.666667, 38.333333],
    )

    timestamps = probe_opencv_frame_timestamps(
        Path("clip.mp4"),
        capture_factory=lambda _path: capture,
    )

    assert timestamps[0] == 0.0
    assert timestamp_intervals(timestamps) == pytest.approx([1 / 30, 1 / 60], abs=1e-6)


def test_wrong_dimensions_are_rejected() -> None:
    with pytest.raises(CanonicalFrameError, match="Unexpected decoded dimensions"):
        apply_canonical_transform(np.zeros((3, 3, 3), dtype=np.uint8), manifest())


def test_point_transform_matches_homography_canonical_space() -> None:
    x_pixel, y_pixel = transform_point_to_canonical(0.0, 3.0, manifest())

    assert (x_pixel, y_pixel) == (3.0, 1.0)
    assert 0 <= x_pixel < manifest().canonical_width
    assert 0 <= y_pixel < manifest().canonical_height


def test_reader_rejects_frame_count_change() -> None:
    capture = FakeCapture("unused", [decoded_frame(), decoded_frame()])

    with pytest.raises(CanonicalFrameError, match="Expected 3 decoded frames"):
        list(
            iter_canonical_frames(
                Path("clip.mp4"),
                manifest(),
                timestamps=[0.0, 0.02, 0.04],
                capture_factory=lambda _path: capture,
            )
        )
