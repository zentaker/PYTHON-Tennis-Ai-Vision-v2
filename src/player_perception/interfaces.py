"""Swappable detector/tracker/pose interfaces; no model-specific imports."""

from __future__ import annotations

from typing import Protocol, Sequence

from .schemas import PlayerDetection, PlayerPose, PlayerTrack


class PersonDetector(Protocol):
    def detect(self, frame_id: int, image) -> Sequence[PlayerDetection]: ...


class MultiObjectTracker(Protocol):
    def update(
        self, frame_id: int, detections: Sequence[PlayerDetection]
    ) -> Sequence[PlayerTrack]: ...


class PoseEstimator(Protocol):
    def estimate(
        self, frame_id: int, image, tracks: Sequence[PlayerTrack]
    ) -> Sequence[PlayerPose]: ...


class RacketEstimator(Protocol):
    def estimate(self, frame_id: int, image, poses: Sequence[PlayerPose]) -> dict[str, object]: ...


class PerceptionBackend(Protocol):
    name: str

    def process(
        self, frame_id: int, image
    ) -> tuple[Sequence[PlayerDetection], Sequence[PlayerTrack], Sequence[PlayerPose]]: ...
