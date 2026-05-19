from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from src.court.extract_reference_frame import extract_reference_frame


def test_extract_reference_frame_writes_selected_frame(tmp_path: Path) -> None:
    clip_path = tmp_path / "clip.mov"
    output_path = tmp_path / "frame.png"

    writer = cv2.VideoWriter(
        str(clip_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        10.0,
        (16, 12),
    )
    assert writer.isOpened()
    writer.write(np.full((12, 16, 3), 0, dtype=np.uint8))
    writer.write(np.full((12, 16, 3), 255, dtype=np.uint8))
    writer.release()

    shape = extract_reference_frame(clip_path, output_path, frame_index=1)

    assert shape == (12, 16, 3)
    assert output_path.exists()
    image = cv2.imread(str(output_path))
    assert image is not None
    assert image.mean() > 240


def test_extract_reference_frame_rejects_negative_frame_index(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="frame_index"):
        extract_reference_frame(tmp_path / "clip.mov", tmp_path / "frame.png", frame_index=-1)
