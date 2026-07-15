from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

from src.tracker.wasb_runner import (
    Detection,
    build_inference_report,
    draw_detection,
    infer_canonical_frames,
    parse_args,
    read_detection_csv,
    write_inference_report,
    write_vfr_concat_file,
)
from src.video.canonical_frames import CanonicalFrame
from src.project.clip_manifest import ClipManifest


class FakePredictor:
    def __call__(self, frames_bgr: list[np.ndarray]) -> tuple[float, float, float]:
        assert len(frames_bgr) == 3
        return 2.0, 1.0, 0.9


def fake_frames(count: int = 527) -> list[CanonicalFrame]:
    timestamps = []
    current = 0.0
    for frame_id in range(count):
        timestamps.append(current)
        current += 1 / 60 if frame_id % 2 == 0 else 1 / 30
    return [
        CanonicalFrame(
            frame_id=frame_id,
            timestamp_seconds=timestamps[frame_id],
            image_bgr=np.zeros((2, 4, 3), dtype=np.uint8),
        )
        for frame_id in range(count)
    ]


def test_fake_predictor_writes_527_vfr_rows_without_torch(tmp_path: Path) -> None:
    output_csv = tmp_path / "data" / "clips" / "nivel_a2_01" / "wasb_detections.csv"

    metrics = infer_canonical_frames(
        fake_frames(),
        FakePredictor(),
        output_csv,
        confidence_threshold=0.5,
        expected_frames=527,
        canonical_width=4,
        canonical_height=2,
    )

    with output_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 527
    assert [int(row["frame_id"]) for row in rows] == list(range(527))
    assert len({round(float(rows[i + 1]["timestamp_seconds"]) - float(rows[i]["timestamp_seconds"]), 6) for i in range(526)}) == 2
    assert all(row["detected"] == "true" for row in rows)
    assert all(0 <= float(row["x_pixel"]) < 4 for row in rows)
    assert all(0 <= float(row["y_pixel"]) < 2 for row in rows)
    assert metrics["processed_frames"] == 527
    assert metrics["median_confidence"] == pytest.approx(0.9)


def test_inference_report_contains_required_external_metadata(tmp_path: Path) -> None:
    output_csv = tmp_path / "wasb_detections.csv"
    metrics = infer_canonical_frames(
        fake_frames(3),
        FakePredictor(),
        output_csv,
        confidence_threshold=0.5,
        expected_frames=3,
        canonical_width=4,
        canonical_height=2,
    )
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
    output_overlay = tmp_path / "overlay.mp4"
    report = build_inference_report(
        metrics,
        read_detection_csv(output_csv),
        manifest,
        device="cuda:0",
        pytorch_version="test-version",
        cuda_version="test-cuda",
        output_csv=output_csv,
        output_overlay=output_overlay,
        total_elapsed_seconds=2.0,
    )
    output_report = tmp_path / "inference_report.json"

    write_inference_report(output_report, report)

    assert output_report.exists()
    assert report["frames_expected"] == report["frames_processed"] == 3
    assert report["confidence_mean"] == pytest.approx(0.9)
    assert report["confidence_median"] == pytest.approx(0.9)
    assert report["device"] == "cuda:0"
    assert report["pytorch_version"] == "test-version"
    assert report["cuda_version"] == "test-cuda"
    assert report["timestamp_verification"]["monotonic"] is True


def test_high_confidence_point_outside_bounds_is_rejected(tmp_path: Path) -> None:
    class InvalidPredictor:
        def __call__(self, _frames: list[np.ndarray]) -> tuple[float, float, float]:
            return 4.0, 1.0, 0.9

    with pytest.raises(ValueError, match="outside canonical bounds"):
        infer_canonical_frames(
            fake_frames(1),
            InvalidPredictor(),
            tmp_path / "detections.csv",
            confidence_threshold=0.5,
            expected_frames=1,
            canonical_width=4,
            canonical_height=2,
        )


def test_overlay_keeps_canonical_dimensions() -> None:
    detection = Detection(0, 0.0, 2.0, 1.0, 0.9, True, 4, 2)

    overlay = draw_detection(np.zeros((2, 4, 3), dtype=np.uint8), detection)

    assert overlay.shape == (2, 4, 3)


def test_vfr_concat_file_preserves_variable_durations(tmp_path: Path) -> None:
    images = [tmp_path / f"frame_{index}.png" for index in range(3)]
    output = tmp_path / "frames.ffconcat"

    write_vfr_concat_file(images, [0.0, 1 / 60, 1 / 20], output)

    contents = output.read_text(encoding="utf-8")
    assert "duration 0.016666667" in contents
    assert "duration 0.033333333" in contents
    assert contents.count("file '") == 3


def test_cli_accepts_explicit_a2_mp4_paths() -> None:
    args = parse_args(
        [
            "--video",
            "data/clips/nivel_a2_01/source.mp4",
            "--manifest",
            "data/clips/nivel_a2_01/clip_manifest.json",
            "--checkpoint",
            "models/wasb/wasb_tennis_best.pth.tar",
            "--wasb-root",
            "third_party/WASB-SBDT",
            "--output-csv",
            "data/clips/nivel_a2_01/wasb_detections.csv",
            "--output-overlay",
            "outputs/nivel_a2_01/stage_2/wasb_detections_overlay.mp4",
            "--output-report",
            "outputs/nivel_a2_01/stage_2/inference_report.json",
            "--device",
            "cuda",
        ]
    )

    assert args.video.suffix == ".mp4"
    assert "nivel_a2_01" in str(args.output_csv)
    assert args.output_report.name == "inference_report.json"


def test_runner_source_has_no_historical_clip_hardcode() -> None:
    source = Path("src/tracker/wasb_runner.py").read_text(encoding="utf-8")

    assert "madrid_R1" not in source
    assert "data/reference_clip" not in source
    assert "import torch" not in source.split("def load_wasb_predictor", maxsplit=1)[0]
