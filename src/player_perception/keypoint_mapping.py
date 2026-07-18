"""Dataset-meta driven keypoint names for body and whole-body pose models."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


COCO_BODY_KEYPOINTS = (
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)


class KeypointMappingError(ValueError):
    """Raised when model output and declared dataset metainfo disagree."""


def names_from_dataset_meta(meta: Any) -> tuple[str, ...] | None:
    if meta is None:
        return None
    if isinstance(meta, dict):
        for key in ("keypoint_name", "keypoint_names"):
            names = meta.get(key)
            if isinstance(names, Sequence) and not isinstance(names, (str, bytes)):
                return tuple(str(name) for name in names)
    for key in ("keypoint_name", "keypoint_names"):
        names = getattr(meta, key, None)
        if isinstance(names, Sequence) and not isinstance(names, (str, bytes)):
            return tuple(str(name) for name in names)
    return None


def resolve_keypoint_names(
    *, expected_count: int, dataset_meta: Any = None, manifest_names: Sequence[str] | None = None
) -> tuple[str, ...]:
    names = names_from_dataset_meta(dataset_meta) or tuple(manifest_names or ())
    if not names:
        if expected_count == len(COCO_BODY_KEYPOINTS):
            return COCO_BODY_KEYPOINTS
        raise KeypointMappingError(
            f"whole-body output declares {expected_count} keypoints but provides no dataset metainfo"
        )
    if len(names) != expected_count:
        raise KeypointMappingError(
            f"dataset metainfo has {len(names)} names but model declares {expected_count} keypoints"
        )
    if expected_count > len(COCO_BODY_KEYPOINTS) and len(names) == len(COCO_BODY_KEYPOINTS):
        raise KeypointMappingError(
            "whole-body mapping cannot be truncated to the 17-point COCO body set"
        )
    return tuple(names)
