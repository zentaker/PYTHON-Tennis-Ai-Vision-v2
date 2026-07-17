"""Lazy, manifest-driven OpenMMLab detector/tracker/pose backend.

The module is import-safe on the Mac development environment. OpenMMLab and torch are
only imported when a real backend is constructed without ``validate_only``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

from ..keypoint_mapping import KeypointMappingError, resolve_keypoint_names
from ..model_bundle import load_model_bundle, resolve_model_path
from ..schemas import (
    BoundingBox,
    FrameInput,
    PlayerDetection,
    PlayerPose,
    PlayerTrack,
    PoseKeypoint,
)


class OpenMMLabRuntimeError(RuntimeError):
    """Raised for an actionable missing dependency, config or model asset."""


@dataclass
class _TrackState:
    track_id: str
    bbox: BoundingBox
    missed: int = 0


class SimpleIoUTracker:
    """Small dependency-free fallback; this is not the ByteTrack algorithm.

    This keeps the backend executable when MMTracking is not installed. A future
    runtime gate must replace this with an official/validated ByteTrack implementation
    before tracking quality is evaluated.
    """

    def __init__(self, high_threshold: float, low_threshold: float, match_threshold: float):
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.match_threshold = match_threshold
        self._states: list[_TrackState] = []
        self._next_id = 1

    @staticmethod
    def _iou(left: BoundingBox, right: BoundingBox) -> float:
        x1, y1 = max(left.x1, right.x1), max(left.y1, right.y1)
        x2, y2 = min(left.x2, right.x2), min(left.y2, right.y2)
        intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        area_left = max(0.0, left.x2 - left.x1) * max(0.0, left.y2 - left.y1)
        area_right = max(0.0, right.x2 - right.x1) * max(0.0, right.y2 - right.y1)
        union = area_left + area_right - intersection
        return intersection / union if union else 0.0

    def update(
        self, frame_id: int, detections: Sequence[PlayerDetection]
    ) -> tuple[PlayerTrack, ...]:
        eligible = [item for item in detections if item.bbox.confidence >= self.low_threshold]
        unmatched = set(range(len(eligible)))
        assigned: list[PlayerTrack] = []
        for state in sorted(self._states, key=lambda item: item.track_id):
            candidates = [
                index
                for index in unmatched
                if self._iou(state.bbox, eligible[index].bbox) >= self.match_threshold
            ]
            if candidates:
                index = max(candidates, key=lambda item: self._iou(state.bbox, eligible[item].bbox))
                detection = eligible[index]
                unmatched.remove(index)
                state.bbox = detection.bbox
                state.missed = 0
                assigned.append(
                    PlayerTrack(
                        frame_id,
                        state.track_id,
                        detection.bbox,
                        confidence=detection.bbox.confidence,
                    )
                )
            else:
                state.missed += 1
        self._states = [state for state in self._states if state.missed <= 30]
        for index in sorted(unmatched):
            detection = eligible[index]
            track_id = f"track_{self._next_id:04d}"
            self._next_id += 1
            self._states.append(_TrackState(track_id, detection.bbox))
            assigned.append(
                PlayerTrack(
                    frame_id, track_id, detection.bbox, confidence=detection.bbox.confidence
                )
            )
        return tuple(sorted(assigned, key=lambda item: item.track_id))


def _resolve_device(requested: str) -> str:
    if requested in {"cpu", "cuda"}:
        return requested
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _as_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    elif hasattr(value, "cpu") and hasattr(value, "numpy"):
        value = value.cpu().numpy()
    return np.asarray(value)


def _prediction_fields(result: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    instances = getattr(result, "pred_instances", result)
    if isinstance(result, (tuple, list)) and result and not hasattr(result, "pred_instances"):
        instances = result[0]
    boxes = getattr(instances, "bboxes", getattr(instances, "boxes", None))
    scores = getattr(instances, "scores", None)
    labels = getattr(instances, "labels", None)
    if boxes is None and isinstance(instances, (tuple, list)) and len(instances) >= 2:
        boxes, scores = instances[0], instances[1]
    if boxes is None:
        raise OpenMMLabRuntimeError("detector output has no bounding boxes")
    boxes_array = _as_numpy(boxes)
    if boxes_array.ndim == 2 and boxes_array.shape[1] >= 5 and scores is None:
        scores = boxes_array[:, 4]
        boxes_array = boxes_array[:, :4]
    scores_array = _as_numpy(scores if scores is not None else np.ones(len(boxes_array)))
    labels_array = _as_numpy(
        labels if labels is not None else np.zeros(len(boxes_array), dtype=int)
    )
    return boxes_array, scores_array, labels_array


def _keypoints_from_result(
    result: Any,
    track_id: str,
    frame_id: int,
    names: Sequence[str],
    bbox: BoundingBox | None = None,
) -> PlayerPose:
    instances = getattr(result, "pred_instances", result)
    keypoints = getattr(instances, "keypoints", None)
    scores = getattr(instances, "keypoint_scores", getattr(instances, "keypoints_scores", None))
    if keypoints is None:
        raise OpenMMLabRuntimeError("pose output has no keypoints")
    points = _as_numpy(keypoints)
    if points.ndim == 3:
        points = points[0]
    if bbox is not None and len(points) and float(np.max(points[:, :2])) <= 1.0:
        points = points.copy()
        points[:, 0] = bbox.x1 + points[:, 0] * (bbox.x2 - bbox.x1)
        points[:, 1] = bbox.y1 + points[:, 1] * (bbox.y2 - bbox.y1)
    score_array = (
        _as_numpy(scores)[0]
        if scores is not None and _as_numpy(scores).ndim == 2
        else (_as_numpy(scores) if scores is not None else np.ones(len(points)))
    )
    if len(points) != len(names):
        raise OpenMMLabRuntimeError(
            f"pose output has {len(points)} keypoints but dataset metainfo declares {len(names)}"
        )
    normalized = tuple(
        PoseKeypoint(
            name,
            float(point[0]),
            float(point[1]),
            float(score_array[index]),
            bool(score_array[index] > 0.05),
        )
        for index, (name, point) in enumerate(zip(names, points))
        if len(point) >= 2
    )
    confidence = float(np.mean([point.confidence for point in normalized])) if normalized else 0.0
    return PlayerPose(frame_id, track_id, normalized, confidence)


class OpenMMLabBackend:
    name = "openmmlab"

    def __init__(
        self,
        model_bundle: Path | str | None = None,
        models_dir: Path | str = "/models",
        config_root: Path | str = ".",
        device: str = "auto",
        validate_only: bool = False,
        init_detector_fn: Callable[..., Any] | None = None,
        inference_detector_fn: Callable[..., Any] | None = None,
        init_pose_fn: Callable[..., Any] | None = None,
        inference_pose_fn: Callable[..., Any] | None = None,
    ):
        self.model_bundle_path = Path(model_bundle) if model_bundle else None
        self.models_dir = Path(models_dir)
        self.config_root = Path(config_root)
        self.device = _resolve_device(device)
        self.bundle = load_model_bundle(self.model_bundle_path) if self.model_bundle_path else None
        self._detector = None
        self._pose = None
        self._inference_detector = inference_detector_fn
        self._inference_pose = inference_pose_fn
        self._init_detector = init_detector_fn
        self._init_pose = init_pose_fn
        self._keypoint_names: tuple[str, ...] | None = None
        tracker_config = (self.bundle or {}).get("tracker", {})
        self.tracker = SimpleIoUTracker(
            float(tracker_config.get("high_threshold", 0.55)),
            float(tracker_config.get("low_threshold", 0.10)),
            float(tracker_config.get("match_threshold", 0.80)),
        )
        if validate_only:
            if self.bundle is None:
                raise OpenMMLabRuntimeError("--validate-only requires --model-bundle")
            return
        if self.bundle is None:
            raise RuntimeError(
                "OpenMMLab extras are not installed or configured; provide --model-bundle and GPU runtime"
            )
        self._load_models()

    def _load_models(self) -> None:
        detector_config = self._resolve_config(self.bundle["detector"]["config"])
        pose_config = self._resolve_config(self.bundle["pose"]["config"])
        detector_checkpoint = resolve_model_path(
            self.models_dir, self.bundle["detector"]["checkpoint"]
        )
        pose_checkpoint = resolve_model_path(self.models_dir, self.bundle["pose"]["checkpoint"])
        for label, path in (
            ("detector config", detector_config),
            ("pose config", pose_config),
            ("detector checkpoint", detector_checkpoint),
            ("pose checkpoint", pose_checkpoint),
        ):
            if not path.is_file():
                raise OpenMMLabRuntimeError(f"missing {label}: {path}")
        if self._init_detector is None or self._init_pose is None:
            try:
                from mmdet.apis import inference_detector, init_detector
                from mmpose.apis import inference_topdown, init_model
            except ImportError as exc:
                raise OpenMMLabRuntimeError(
                    "OpenMMLab runtime missing; install pinned MMEngine/MMCV/MMDetection/MMPose extras"
                ) from exc
            self._init_detector = init_detector
            self._inference_detector = self._inference_detector or inference_detector
            self._init_pose = init_model
            self._inference_pose = self._inference_pose or inference_topdown
        self._detector = self._init_detector(
            str(detector_config), str(detector_checkpoint), device=self.device
        )
        self._pose = self._init_pose(str(pose_config), str(pose_checkpoint), device=self.device)
        expected_count = int(self.bundle["pose"]["keypoint_count"])
        try:
            self._keypoint_names = resolve_keypoint_names(
                expected_count=expected_count,
                dataset_meta=getattr(self._pose, "dataset_meta", None),
                manifest_names=self.bundle["pose"].get("keypoint_names"),
            )
        except KeypointMappingError as exc:
            raise OpenMMLabRuntimeError(str(exc)) from exc

    def _resolve_config(self, relative_path: str) -> Path:
        repository_path = (self.config_root / relative_path).resolve()
        if repository_path.is_file():
            return repository_path
        mounted_path = resolve_model_path(self.models_dir, relative_path)
        return mounted_path

    @property
    def initialized(self) -> bool:
        return self._detector is not None and self._pose is not None

    def process(
        self, frame: FrameInput
    ) -> tuple[tuple[PlayerDetection, ...], tuple[PlayerTrack, ...], tuple[PlayerPose, ...]]:
        if not isinstance(frame, FrameInput) or frame.image is None:
            raise ValueError(
                "OpenMMLabBackend requires a decoded FrameInput image; image=None is invalid"
            )
        if not self.initialized or self._inference_detector is None or self._inference_pose is None:
            raise OpenMMLabRuntimeError(
                "OpenMMLab backend is not initialized; use a model bundle and runtime"
            )
        result = self._inference_detector(self._detector, frame.image)
        boxes, scores, labels = _prediction_fields(result)
        threshold = float(self.bundle["detector"].get("confidence_threshold", 0.35))
        detections = tuple(
            PlayerDetection(
                frame.frame_id, f"det_{index:04d}", BoundingBox(*map(float, box[:4]), float(score))
            )
            for index, (box, score, label) in enumerate(zip(boxes, scores, labels))
            if int(label) == 0 and float(score) >= threshold
        )
        tracks = self.tracker.update(frame.frame_id, detections)
        poses: list[PlayerPose] = []
        if tracks:
            bboxes = np.asarray(
                [[track.bbox.x1, track.bbox.y1, track.bbox.x2, track.bbox.y2] for track in tracks],
                dtype=np.float32,
            )
            pose_results = self._inference_pose(self._pose, frame.image, bboxes)
            if len(pose_results) != len(tracks):
                raise OpenMMLabRuntimeError(
                    f"pose output count {len(pose_results)} does not match track count {len(tracks)} at frame {frame.frame_id}"
                )
            if self._keypoint_names is None:
                raise OpenMMLabRuntimeError("pose keypoint metainfo was not initialized")
            poses = [
                _keypoints_from_result(
                    item, track.track_id, frame.frame_id, self._keypoint_names, track.bbox
                )
                for item, track in zip(pose_results, tracks)
            ]
        return detections, tracks, tuple(poses)

    def close(self) -> None:
        self._detector = None
        self._pose = None
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
