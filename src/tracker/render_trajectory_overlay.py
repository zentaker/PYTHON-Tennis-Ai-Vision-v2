"""Render legacy CFR or canonical VFR Stage 3 trajectory overlays."""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np

from src.project.clip_manifest import ClipManifest
from src.video.canonical_frames import CanonicalFrame, iter_canonical_frames
from src.video.vfr_overlay import render_canonical_vfr_overlay


RAW_COLOR = (0, 255, 255)
SMOOTH_COLOR = (0, 0, 255)
INTERPOLATED_COLOR = (255, 0, 255)
REJECTED_COLOR = (0, 165, 255)
MISSING_COLOR = (180, 180, 180)
TRAIL_COLOR = (255, 255, 255)


def _point(row: dict, x_key: str, y_key: str) -> tuple[int, int] | None:
    x_value = row.get(x_key)
    y_value = row.get(y_key)
    if x_value is None or y_value is None:
        return None
    if not np.isfinite(x_value) or not np.isfinite(y_value):
        return None
    return int(round(x_value)), int(round(y_value))


def _source_color(source: str) -> tuple[int, int, int]:
    if source == "detected":
        return SMOOTH_COLOR
    if source == "interpolated":
        return INTERPOLATED_COLOR
    if source == "rejected":
        return REJECTED_COLOR
    return MISSING_COLOR


def draw_trajectory_frame(
    frame_bgr: np.ndarray,
    row: dict,
    trail: deque[tuple[int, int]],
    *,
    debug: bool,
) -> np.ndarray:
    """Draw raw, smooth, source/reason and a recent trail in canonical coordinates."""
    frame = frame_bgr.copy()
    raw_point = _point(row, "x_raw", "y_raw")
    smooth_point = _point(row, "x_smooth", "y_smooth")
    source = row["source"]
    source_color = _source_color(source)
    if raw_point is not None:
        cv2.circle(frame, raw_point, 6, RAW_COLOR, 1)
        if debug:
            cv2.drawMarker(
                frame,
                raw_point,
                RAW_COLOR,
                markerType=cv2.MARKER_CROSS,
                markerSize=14,
                thickness=1,
            )
    if smooth_point is not None:
        trail.append(smooth_point)
        cv2.circle(frame, smooth_point, 8, source_color, 2)
    elif source == "missing":
        trail.clear()
    if len(trail) >= 2:
        cv2.polylines(frame, [np.array(trail, dtype=np.int32)], False, TRAIL_COLOR, 1)

    timestamp = row.get("timestamp_seconds")
    time_label = f" | t={timestamp:.3f}s" if timestamp is not None else ""
    label = f"frame {row['frame_id']}{time_label} | {source}"
    cv2.putText(
        frame,
        label,
        (24, 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        source_color,
        2,
        cv2.LINE_AA,
    )
    if debug:
        details = f"conf={row['confidence']:.3f} reason={row['reason'] or '-'}"
        cv2.putText(
            frame,
            details,
            (24, 72),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        legend = "raw=yellow | smooth=red | interpolated=magenta | rejected=orange"
        cv2.putText(
            frame,
            legend,
            (24, frame.shape[0] - 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
    return frame


def _render_legacy_cfr_overlay(
    video_path: Path,
    rows: list[dict],
    output_mp4: Path,
    *,
    debug: bool,
    trail_length: int,
) -> dict[str, float | int | str]:
    """Keep the historical Madrid OpenCV CFR path unchanged for compatibility."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    writer = cv2.VideoWriter(
        str(output_mp4), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"Could not open output video writer: {output_mp4}")
    rows_by_frame = {int(row["frame_id"]): row for row in rows}
    trail: deque[tuple[int, int]] = deque(maxlen=trail_length)
    frame_id = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        row = rows_by_frame.get(frame_id)
        if row is not None:
            frame = draw_trajectory_frame(frame, row, trail, debug=debug)
        writer.write(frame)
        frame_id += 1
    cap.release()
    writer.release()
    check = cv2.VideoCapture(str(output_mp4))
    ok, _ = check.read()
    check.release()
    if not ok:
        raise RuntimeError(f"Overlay MP4 was written but could not be read: {output_mp4}")
    return {
        "mode": "legacy_cfr",
        "frames": frame_id,
        "width": width,
        "height": height,
        "duration_seconds": frame_id / fps,
    }


def render_trajectory_overlay(
    video_path: Path,
    rows: list[dict],
    output_mp4: Path,
    *,
    debug: bool = False,
    trail_length: int = 18,
    manifest: ClipManifest | None = None,
    timestamps: Sequence[float] | None = None,
) -> dict[str, float | int | str]:
    """Render a historical CFR overlay or an orientation-safe timestamp-driven VFR one."""
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    if manifest is None:
        return _render_legacy_cfr_overlay(
            video_path,
            rows,
            output_mp4,
            debug=debug,
            trail_length=trail_length,
        )
    if timestamps is None:
        raise ValueError("Canonical VFR rendering requires explicit timestamps")
    if len(rows) != manifest.frames_total or len(timestamps) != manifest.frames_total:
        raise ValueError("Rows/timestamps do not match manifest frames_total")
    rows_by_frame = {int(row["frame_id"]): row for row in rows}
    trail: deque[tuple[int, int]] = deque(maxlen=trail_length)

    def render(record: CanonicalFrame) -> np.ndarray:
        row = rows_by_frame.get(record.frame_id)
        if row is None:
            raise ValueError(f"Missing trajectory row for frame {record.frame_id}")
        row_timestamp = row.get("timestamp_seconds")
        if row_timestamp is not None and not math.isclose(
            float(row_timestamp), record.timestamp_seconds, abs_tol=5e-10
        ):
            raise ValueError("Trajectory timestamp differs from canonical frame timestamp")
        return draw_trajectory_frame(record.image_bgr, row, trail, debug=debug)

    metadata = render_canonical_vfr_overlay(
        iter_canonical_frames(video_path, manifest, timestamps=timestamps),
        output_mp4,
        render,
        expected_frames=manifest.frames_total,
        expected_width=manifest.canonical_width,
        expected_height=manifest.canonical_height,
    )
    return {"mode": "canonical_vfr", **metadata}
