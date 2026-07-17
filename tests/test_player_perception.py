from __future__ import annotations

from pathlib import Path
import subprocess

from src.player_perception.backends.mock_backend import MockBackend
from src.player_perception.biomechanics import geometric_features
from src.player_perception.court_projection import CourtProjector
from src.player_perception.foot_anchor import foot_anchor
from src.player_perception.foot_anchor import FootAnchorSmoother
from src.player_perception.identity import assign_near_far, stable_identity_history
from src.player_perception.pipeline import PerceptionPipeline
from src.player_perception.schemas import BoundingBox, PlayerPose, PlayerTrack, PoseKeypoint


ROOT = Path(__file__).resolve().parents[1]


def test_mock_backend_is_deterministic_and_has_two_tracks() -> None:
    backend = MockBackend()
    first = backend.process(4)
    second = backend.process(4)
    assert first == second
    assert len(first[1]) == 2


def test_identity_uses_court_sign_and_history() -> None:
    box = BoundingBox(0, 0, 10, 10, 1.0)
    tracks = [PlayerTrack(0, "a", box), PlayerTrack(0, "b", box)]
    assigned = assign_near_far(tracks, {"a": -3.0, "b": 4.0})
    assert [item.identity for item in assigned] == ["near", "far"]
    assert stable_identity_history({"a": ["near", "near", "far"]})["a"] == "near"


def test_foot_anchor_priority_and_bbox_fallback() -> None:
    box = BoundingBox(10, 20, 30, 60, 0.8)
    pose = PlayerPose(
        0,
        "a",
        (PoseKeypoint("left_ankle", 12, 59, 0.9), PoseKeypoint("right_ankle", 28, 58, 0.9)),
        0.9,
    )
    anchor = foot_anchor(0, "a", box, pose)
    assert anchor.method == "pose_ankle"
    assert anchor.support_side == "both"
    assert foot_anchor(0, "a", box).fallback_used


def test_foot_anchor_prefers_heel_or_toe_over_ankle() -> None:
    box = BoundingBox(10, 20, 30, 60, 0.8)
    pose = PlayerPose(
        0,
        "a",
        (PoseKeypoint("left_toe", 12, 59, 0.9), PoseKeypoint("right_ankle", 28, 58, 0.9)),
        0.9,
    )
    anchor = foot_anchor(0, "a", box, pose)
    assert anchor.method == "pose_heel-toe"
    assert anchor.support_side == "left"


def test_foot_anchor_smoother_is_causal_and_marks_smoothing() -> None:
    box = BoundingBox(10, 20, 30, 60, 0.8)
    smoother = FootAnchorSmoother(window=2)
    first = smoother.update(foot_anchor(0, "a", box))
    second = smoother.update(foot_anchor(1, "a", BoundingBox(20, 20, 40, 60, 0.8)))
    assert first.smoothing_applied is False
    assert second.smoothing_applied is True
    assert second.x_pixel == 25.0


def test_projection_regions_and_mock_pipeline() -> None:
    projector = CourtProjector(ROOT / "data/clips/nivel_a2_01/homography.json")
    report = PerceptionPipeline(MockBackend(), projector).run(range(3))
    assert report.frame_count == 3
    assert len(report.frames[0].court_positions) == 2
    assert all(position.track_id for position in report.frames[0].court_positions)


def test_biomechanical_angle_confidence() -> None:
    pose = PlayerPose(
        0,
        "a",
        tuple(
            PoseKeypoint(name, float(i), float(i % 3), 0.8)
            for i, name in enumerate(
                (
                    "left_hip",
                    "left_knee",
                    "left_ankle",
                    "right_hip",
                    "right_knee",
                    "right_ankle",
                    "left_shoulder",
                    "left_elbow",
                    "left_wrist",
                    "right_shoulder",
                    "right_elbow",
                    "right_wrist",
                )
            )
        ),
        0.8,
    )
    features = geometric_features(pose)
    assert features["left_knee_flexion"]["status"] == "VALID"
    assert features["left_knee_flexion"]["confidence"] == 0.8


def test_openmmlab_import_is_lazy_and_clear() -> None:
    from src.player_perception.backends.openmmlab_backend import OpenMMLabBackend

    try:
        OpenMMLabBackend(device="cpu")
    except RuntimeError as exc:
        assert "extras are not installed" in str(exc)


def test_cli_mock_smoke(tmp_path) -> None:
    command = [
        "uv",
        "run",
        "python",
        "-m",
        "src.player_perception.cli",
        "--backend",
        "mock",
        "--device",
        "cpu",
        "--start-frame",
        "0",
        "--end-frame",
        "2",
        "--output-dir",
        str(tmp_path),
    ]
    result = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    assert '"frames": 3' in result.stdout
    assert (tmp_path / "perception_report.json").is_file()
