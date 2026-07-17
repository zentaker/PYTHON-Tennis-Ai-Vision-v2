"""CPU-safe perception pipeline orchestration."""

from __future__ import annotations

from .court_projection import CourtProjector
from .foot_anchor import FootAnchorSmoother, foot_anchor
from .identity import assign_near_far
from .schemas import FramePerception, PerceptionReport
from .schemas import FrameInput


class PerceptionPipeline:
    def __init__(self, backend, projector: CourtProjector, foot_smoothing_window: int = 1):
        self.backend = backend
        self.projector = projector
        self.previous = {}
        self.foot_smoother = (
            FootAnchorSmoother(foot_smoothing_window) if foot_smoothing_window > 1 else None
        )

    def process_frame(
        self, frame: FrameInput | int, image=None, timestamp_seconds: float | None = None
    ) -> FramePerception:
        if isinstance(frame, int):
            height, width = image.shape[:2] if image is not None else (0, 0)
            frame = FrameInput(
                frame_id=frame,
                timestamp_seconds=float(
                    timestamp_seconds if timestamp_seconds is not None else frame
                ),
                image=image,
                width=width,
                height=height,
            )
        detections, tracks, poses = self.backend.process(frame)
        pose_by_track = {pose.track_id: pose for pose in poses}
        anchors = tuple(
            foot_anchor(
                frame.frame_id, track.track_id, track.bbox, pose_by_track.get(track.track_id)
            )
            for track in tracks
        )
        if self.foot_smoother:
            anchors = tuple(self.foot_smoother.update(anchor) for anchor in anchors)
        positions = tuple(self.projector.project(anchor) for anchor in anchors)
        y_by_track = {position.track_id: position.y_m for position in positions}
        tracks = tuple(assign_near_far(list(tracks), y_by_track, self.previous))
        self.previous = {track.track_id: track.identity for track in tracks}
        return FramePerception(
            frame.frame_id,
            tuple(detections),
            tracks,
            tuple(poses),
            anchors,
            positions,
            frame.timestamp_seconds,
            frame.width,
            frame.height,
        )

    def run(
        self, frame_ids, *, clip_id: str = "nivel_a2_01", device: str = "cpu"
    ) -> PerceptionReport:
        frames = [
            self.process_frame(frame)
            if isinstance(frame, FrameInput)
            else self.process_frame(frame)
            for frame in frame_ids
        ]
        return PerceptionReport(
            clip_id=clip_id,
            backend=self.backend.name,
            device=device,
            frame_count=len(frames),
            frames=frames,
        )
