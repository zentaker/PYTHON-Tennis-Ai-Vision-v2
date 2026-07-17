"""CPU-safe perception pipeline orchestration."""

from __future__ import annotations

from .court_projection import CourtProjector
from .foot_anchor import foot_anchor
from .identity import assign_near_far
from .schemas import FramePerception, PerceptionReport


class PerceptionPipeline:
    def __init__(self, backend, projector: CourtProjector):
        self.backend = backend
        self.projector = projector
        self.previous = {}

    def process_frame(self, frame_id: int, image=None) -> FramePerception:
        detections, tracks, poses = self.backend.process(frame_id, image)
        pose_by_track = {pose.track_id: pose for pose in poses}
        anchors = tuple(
            foot_anchor(frame_id, track.track_id, track.bbox, pose_by_track.get(track.track_id))
            for track in tracks
        )
        positions = tuple(self.projector.project(anchor) for anchor in anchors)
        y_by_track = {position.track_id: position.y_m for position in positions}
        tracks = tuple(assign_near_far(list(tracks), y_by_track, self.previous))
        self.previous = {track.track_id: track.identity for track in tracks}
        return FramePerception(
            frame_id, tuple(detections), tracks, tuple(poses), anchors, positions
        )

    def run(
        self, frame_ids, *, clip_id: str = "nivel_a2_01", device: str = "cpu"
    ) -> PerceptionReport:
        frames = [self.process_frame(frame_id) for frame_id in frame_ids]
        return PerceptionReport(
            clip_id=clip_id,
            backend=self.backend.name,
            device=device,
            frame_count=len(frames),
            frames=frames,
        )
