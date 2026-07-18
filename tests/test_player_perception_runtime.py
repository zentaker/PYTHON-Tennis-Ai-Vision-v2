from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scripts.validate_stage_p1_outputs import validate
from src.player_perception.backends.openmmlab_backend import OpenMMLabBackend
from src.player_perception.backends.openmmlab_backend import SimpleIoUTracker
from src.player_perception.cli import _selected_frames, build_parser
from src.player_perception.keypoint_mapping import KeypointMappingError, resolve_keypoint_names
from src.player_perception.model_bundle import ModelBundleError, load_model_bundle
from src.player_perception.outputs import write_perception_outputs
from src.player_perception.pipeline import PerceptionPipeline
from src.player_perception.schemas import FrameInput
from src.player_perception.backends.mock_backend import MockBackend
from src.player_perception.court_projection import CourtProjector


ROOT = Path(__file__).resolve().parents[1]


def test_manifest_is_relative_and_model_bundle_is_loadable(tmp_path: Path) -> None:
    payload = load_model_bundle(ROOT / "config/player_perception/p1_openmmlab.json")
    assert payload["pose"]["keypoint_count"] == 133
    assert payload["tracker"]["implementation"] == "simple-iou-fallback"
    with pytest.raises(ModelBundleError, match="relative"):
        payload["detector"]["config"] = "/absolute/config.py"
        temporary = tmp_path / "invalid_p1_model_bundle.json"
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        try:
            load_model_bundle(temporary)
        finally:
            temporary.unlink()


def test_wholebody_mapping_rejects_17_point_truncation() -> None:
    with pytest.raises(KeypointMappingError, match="metainfo"):
        resolve_keypoint_names(expected_count=133, manifest_names=["nose"] * 17)
    names = [f"joint_{index}" for index in range(133)]
    resolved = resolve_keypoint_names(expected_count=133, manifest_names=names)
    assert len(resolved) == 133
    assert isinstance(SimpleIoUTracker(0.5, 0.1, 0.5), SimpleIoUTracker)


def test_pipeline_accepts_real_frame_input_and_preserves_timestamp() -> None:
    image = np.zeros((32, 48, 3), dtype=np.uint8)
    frame = FrameInput(7, 1.25, image, 48, 32)
    projector = CourtProjector(ROOT / "data/clips/nivel_a2_01/homography.json")
    report = PerceptionPipeline(MockBackend(), projector).run([frame])
    assert report.frames[0].timestamp_seconds == 1.25
    assert report.frames[0].width == 48
    assert report.frames[0].height == 32


def test_cli_rejects_mixed_frame_selection_and_out_of_bounds() -> None:
    args = build_parser().parse_args(["--frames", "1,2", "--start-frame", "0"])
    with pytest.raises(ValueError, match="cannot be combined"):
        _selected_frames(args, 10)
    args = build_parser().parse_args(["--frames", "1,10"])
    with pytest.raises(ValueError, match="outside"):
        _selected_frames(args, 10)


def test_openmmlab_fake_backend_initializes_once_and_rejects_none(tmp_path: Path) -> None:
    config_detector = tmp_path / "detector.py"
    config_pose = tmp_path / "pose.py"
    config_detector.write_text("# fake", encoding="utf-8")
    config_pose.write_text("# fake", encoding="utf-8")
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "detector.pth").write_bytes(b"detector")
    (tmp_path / "models" / "pose.pth").write_bytes(b"pose")
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "detector": {
                    "framework": "fake",
                    "config": "detector.py",
                    "config_url": "https://example.invalid/detector.py",
                    "config_sha256": "a" * 64,
                    "checkpoint": "detector.pth",
                    "checkpoint_url": "https://example.invalid/detector.pth",
                    "checksum_sha256": None,
                    "input_size": [32, 32],
                    "confidence_threshold": 0.1,
                    "keypoint_convention": "coco",
                    "keypoint_count": 1,
                },
                "tracker": {
                    "implementation": "simple-iou-fallback",
                    "high_threshold": 0.5,
                    "low_threshold": 0.1,
                    "match_threshold": 0.1,
                },
                "pose": {
                    "framework": "fake",
                    "config": "pose.py",
                    "config_url": "https://example.invalid/pose.py",
                    "config_sha256": "b" * 64,
                    "checkpoint": "pose.pth",
                    "checkpoint_url": "https://example.invalid/pose.pth",
                    "checksum_sha256": None,
                    "input_size": [32, 32],
                    "confidence_threshold": 0.1,
                    "keypoint_convention": "coco",
                    "keypoint_count": 2,
                    "keypoint_names": ["nose", "left_eye"],
                },
                "runtime": {
                    "device": "cpu",
                    "precision": "fp32",
                    "batch_size": 1,
                    "model_cache_path": "cache",
                },
                "license": {"source": "test", "license": "test", "notes": "test"},
            }
        ),
        encoding="utf-8",
    )
    init_calls = {"detector": 0, "pose": 0}

    def init_detector(*_args, **_kwargs):
        init_calls["detector"] += 1
        return object()

    def init_pose(*_args, **_kwargs):
        init_calls["pose"] += 1
        return object()

    class Instances:
        bboxes = np.asarray([[1, 1, 10, 20]], dtype=float)
        scores = np.asarray([0.9])
        labels = np.asarray([0])

    class PoseInstances:
        keypoints = np.asarray([[[5, 20], [6, 19]]], dtype=float)
        keypoint_scores = np.asarray([[0.9, 0.8]])

    backend = OpenMMLabBackend(
        bundle_path,
        tmp_path / "models",
        tmp_path,
        device="cpu",
        init_detector_fn=init_detector,
        init_pose_fn=init_pose,
        inference_detector_fn=lambda *_args: type("Result", (), {"pred_instances": Instances()})(),
        inference_pose_fn=lambda *_args: [
            type("Result", (), {"pred_instances": PoseInstances()})()
        ],
    )
    assert init_calls == {"detector": 1, "pose": 1}
    frame = FrameInput(0, 0.0, np.zeros((32, 48, 3), dtype=np.uint8), 48, 32)
    detections, tracks, poses = backend.process(frame)
    assert len(detections) == len(tracks) == len(poses) == 1
    with pytest.raises(ValueError, match="image=None"):
        backend.process(FrameInput(1, 0.1, None, 48, 32))


def test_outputs_and_validator_cover_all_contract_files(tmp_path: Path) -> None:
    projector = CourtProjector(ROOT / "data/clips/nivel_a2_01/homography.json")
    frame = FrameInput(139, 2.7, np.zeros((32, 48, 3), dtype=np.uint8), 48, 32)
    report = PerceptionPipeline(MockBackend(), projector).run([frame])
    paths = write_perception_outputs(
        report,
        tmp_path,
        events=[
            {
                "id": "ev_001",
                "frame_start": 139,
                "frame_end": 139,
                "frame_mid": 139,
                "player": "near",
            }
        ],
    )
    paths["artifact_manifest.json"] = __import__(
        "src.player_perception.outputs", fromlist=["write_artifact_manifest"]
    ).write_artifact_manifest(paths.values(), tmp_path)
    result = validate(tmp_path, [139])
    assert result["status"] == "VALID"
