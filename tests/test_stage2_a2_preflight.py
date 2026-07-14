from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from scripts.stage2_a2_preflight import run_preflight
from src.project.clip_manifest import ClipManifest


def test_preflight_validates_metadata_without_model(monkeypatch, tmp_path: Path) -> None:
    video_path = tmp_path / "data" / "clips" / "nivel_a2_01" / "source.mp4"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"fake mp4")
    manifest = ClipManifest(
        clip_id="nivel_a2_01",
        source_filename="source.mp4",
        source_extension=".mp4",
        source_sha256="a" * 64,
        fps=50.0,
        frames_total=3,
        duration_seconds=0.05,
        resolution_width=4,
        resolution_height=2,
        codec="hevc",
        camera_mode="fixed",
        status="stage_2_prepared_external",
        container_rotation_degrees=270,
        decoded_width=2,
        decoded_height=4,
        canonical_width=4,
        canonical_height=2,
        canonical_transform="rotate_90_ccw",
        timing_mode="variable_frame_rate",
        notes="test",
    )
    manifest_path = video_path.parent / "clip_manifest.json"
    manifest.write(manifest_path)
    homography_path = video_path.parent / "homography.json"
    homography_path.write_text(
        json.dumps(
            {
                "clip_id": "nivel_a2_01",
                "frame_dimensions": {"width": 4, "height": 2},
            }
        ),
        encoding="utf-8",
    )

    class Capture:
        def isOpened(self) -> bool:
            return True

        def get(self, _property: int) -> float:
            return 3.0

        def read(self) -> tuple[bool, np.ndarray]:
            return True, np.zeros((4, 2, 3), dtype=np.uint8)

        def release(self) -> None:
            return None

    monkeypatch.setattr("scripts.stage2_a2_preflight.sha256_file", lambda _path: "a" * 64)
    monkeypatch.setattr(
        "scripts.stage2_a2_preflight.probe_frame_timestamps",
        lambda _path: [0.0, 1 / 60, 1 / 20],
    )
    monkeypatch.setattr(cv2, "VideoCapture", lambda _path: Capture())

    report = run_preflight(video_path, manifest_path)

    assert report["status"] == "LIGHTWEIGHT_PREFLIGHT_PASSED"
    assert report["inference_executed"] is False
    assert report["frames_manifest"] == report["timestamps_count"] == 3
    assert report["variable_timing_confirmed"] is True
    assert report["canonical_dimensions"] == [4, 2]
    assert report["checkpoint"]["exists"] is False
