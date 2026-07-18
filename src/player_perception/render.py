"""Legible player-aware overlays for a selected frame sequence."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

from .schemas import FrameInput, FramePerception


def _draw_frame(image: np.ndarray, frame: FramePerception) -> np.ndarray:
    canvas = image.copy()
    for track in frame.tracks:
        color = (50, 220, 50) if track.identity == "near" else (50, 120, 240)
        x1, y1, x2, y2 = (
            int(track.bbox.x1),
            int(track.bbox.y1),
            int(track.bbox.x2),
            int(track.bbox.y2),
        )
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 3)
        label = f"{track.track_id} {track.identity}"
        cv2.putText(
            canvas,
            label,
            (x1, max(25, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            color,
            2,
            cv2.LINE_AA,
        )
        pose = next((item for item in frame.poses if item.track_id == track.track_id), None)
        if pose:
            for point in pose.keypoints:
                if point.visible and point.name in {
                    "left_wrist",
                    "right_wrist",
                    "left_ankle",
                    "right_ankle",
                    "left_heel",
                    "right_heel",
                    "left_toe",
                    "right_toe",
                }:
                    cv2.circle(canvas, (int(point.x), int(point.y)), 5, (255, 220, 20), -1)
        anchor = next(
            (item for item in frame.foot_anchors if item.track_id == track.track_id), None
        )
        position = next(
            (item for item in frame.court_positions if item.track_id == track.track_id), None
        )
        if anchor:
            cv2.circle(canvas, (int(anchor.x_pixel), int(anchor.y_pixel)), 9, (0, 255, 255), -1)
        if position:
            text = f"X={position.x_m:.2f} Y={position.y_m:.2f}"
            cv2.putText(
                canvas,
                text,
                (x1, min(canvas.shape[0] - 15, y2 + 28)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                color,
                2,
                cv2.LINE_AA,
            )
    cv2.putText(
        canvas,
        f"frame={frame.frame_id} t={frame.timestamp_seconds:.3f}s",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return canvas


def write_pose_overlay(
    frames: Iterable[FrameInput], perceptions: Iterable[FramePerception], output_path: Path
) -> Path:
    records = list(zip(frames, perceptions))
    if not records:
        raise ValueError("cannot render an empty frame sequence")
    first = records[0][0].image
    height, width = first.shape[:2]
    writer = cv2.VideoWriter(
        str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), 25.0, (width, height)
    )
    if not writer.isOpened():
        raise RuntimeError(f"could not create overlay: {output_path}")
    try:
        for frame, perception in records:
            writer.write(_draw_frame(frame.image, perception))
    finally:
        writer.release()
    return output_path


def write_contact_sheet(
    frames: Iterable[FrameInput], perceptions: Iterable[FramePerception], output_path: Path
) -> Path:
    thumbnails = []
    for frame, perception in zip(frames, perceptions):
        image = _draw_frame(frame.image, perception)
        scale = min(1.0, 640 / image.shape[1])
        thumbnails.append(
            cv2.resize(image, (int(image.shape[1] * scale), int(image.shape[0] * scale)))
        )
    if not thumbnails:
        raise ValueError("cannot render an empty contact sheet")
    width = max(item.shape[1] for item in thumbnails)
    rows = []
    for start in range(0, len(thumbnails), 2):
        row_items = thumbnails[start : start + 2]
        row = np.zeros((max(item.shape[0] for item in row_items), width * 2, 3), dtype=np.uint8)
        offset = 0
        for item in row_items:
            row[: item.shape[0], offset : offset + item.shape[1]] = item
            offset += width
        rows.append(row)
    sheet = np.vstack(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), sheet):
        raise RuntimeError(f"could not write contact sheet: {output_path}")
    return output_path
