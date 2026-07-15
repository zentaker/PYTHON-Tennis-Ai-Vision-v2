from __future__ import annotations

from pathlib import Path

import numpy as np

from src.video.canonical_frames import CanonicalFrame
from src.video.vfr_overlay import render_canonical_vfr_overlay, write_vfr_concat_file


def test_concat_preserves_527_vfr_frames_and_last_frame(tmp_path: Path) -> None:
    images = [tmp_path / f"frame_{index:06d}.png" for index in range(527)]
    timestamps = []
    current = 0.0
    for frame_id in range(527):
        timestamps.append(current)
        current += 1 / 60 if frame_id % 2 == 0 else 1 / 30
    output = tmp_path / "frames.ffconcat"

    write_vfr_concat_file(images, timestamps, output)

    contents = output.read_text(encoding="utf-8")
    assert contents.count("file '") == 527
    assert contents.count("option framerate 1000000") == 527
    assert f"frame_{526:06d}.png" in contents
    assert "duration 0.016666667" in contents
    assert "duration 0.033333333" in contents


def test_canonical_renderer_passes_exact_527_a2_frames_to_encoder(
    monkeypatch, tmp_path: Path
) -> None:
    frame = np.zeros((1536, 2746, 3), dtype=np.uint8)
    captured = {}
    monkeypatch.setattr("src.video.vfr_overlay.cv2.imwrite", lambda _path, _image: True)

    def fake_encode(image_paths, timestamps, _output_path, **kwargs):
        captured["count"] = len(image_paths)
        captured["last"] = image_paths[-1].name
        captured["timestamps"] = timestamps
        captured.update(kwargs)
        return {"frames": 527, "width": 2746, "height": 1536, "duration_seconds": 10.47}

    monkeypatch.setattr("src.video.vfr_overlay.encode_vfr_png_sequence", fake_encode)
    frames = (
        CanonicalFrame(frame_id=index, timestamp_seconds=index / 50, image_bgr=frame)
        for index in range(527)
    )

    metadata = render_canonical_vfr_overlay(
        frames,
        tmp_path / "overlay.mp4",
        lambda record: record.image_bgr,
        expected_frames=527,
        expected_width=2746,
        expected_height=1536,
    )

    assert captured["count"] == 527
    assert captured["last"] == "frame_000526.png"
    assert captured["timestamps"][-1] == 526 / 50
    assert metadata["frames"] == 527
