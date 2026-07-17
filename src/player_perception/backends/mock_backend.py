"""Deterministic two-player backend for CPU tests and smoke runs."""

from __future__ import annotations

from ..schemas import BoundingBox, PlayerDetection, PlayerPose, PlayerTrack, PoseKeypoint


class MockBackend:
    name = "mock"

    def __init__(self, width: int = 2746, height: int = 1536):
        self.width = width
        self.height = height

    def process(self, frame_id: int, image=None):
        del image
        shift = (frame_id % 5) * 0.5
        boxes = [
            BoundingBox(900 + shift, 850, 1100 + shift, 1350, 0.98),
            BoundingBox(1600 - shift, 180, 1800 - shift, 700, 0.97),
        ]
        detections = tuple(
            PlayerDetection(frame_id, f"det_{i}", box) for i, box in enumerate(boxes)
        )
        tracks = tuple(
            PlayerTrack(frame_id, f"track_{i}", box, "unknown", box.confidence)
            for i, box in enumerate(boxes)
        )
        poses = []
        for track in tracks:
            x, y = track.bbox.center
            points = tuple(
                PoseKeypoint(name, x + dx, track.bbox.y2 - dy, 0.9)
                for name, dx, dy in (
                    ("left_ankle", -25, 0),
                    ("right_ankle", 25, 0),
                    ("left_wrist", -55, 260),
                    ("right_wrist", 55, 260),
                    ("left_hip", -25, 170),
                    ("right_hip", 25, 170),
                    ("left_knee", -30, 70),
                    ("right_knee", 30, 70),
                    ("left_shoulder", -35, 270),
                    ("right_shoulder", 35, 270),
                    ("left_elbow", -60, 240),
                    ("right_elbow", 60, 240),
                )
            )
            poses.append(PlayerPose(frame_id, track.track_id, points, 0.9))
        return detections, tracks, tuple(poses)
