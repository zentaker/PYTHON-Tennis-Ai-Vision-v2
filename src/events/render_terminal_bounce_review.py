"""Create a focused canonical review of the final A2 hit and terminal bounce."""

from __future__ import annotations

import csv
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.events.render_events_overlay import draw_events_frame, load_event_rows
from src.project.clip_manifest import ClipManifest
from src.video.canonical_frames import CanonicalFrame, iter_canonical_frames
from src.video.vfr_overlay import render_canonical_vfr_overlay


REVIEW_START_FRAME = 428
REVIEW_END_FRAME = 480
CONTACT_FRAME_IDS = tuple(range(459, 468))


def _load_optional_tracking(path: Path | None) -> dict[int, tuple[float, float]]:
    if path is None or not path.is_file():
        return {}
    tracking: dict[int, tuple[float, float]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            x_value = row.get("x_smooth", "")
            y_value = row.get("y_smooth", "")
            if x_value and y_value:
                tracking[int(row["frame_id"])] = (float(x_value), float(y_value))
    return tracking


def _terminal_events(events: Sequence[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    by_id = {str(event["id"]): event for event in events}
    if "ev_009" not in by_id or "ev_010" not in by_id:
        raise ValueError("Terminal review requires ev_009 and ev_010")
    final_hit = by_id["ev_009"]
    terminal_bounce = by_id["ev_010"]
    if (
        final_hit["type"] != "hit"
        or int(final_hit["frame_start"]) != 434
        or int(final_hit["frame_end"]) != 435
    ):
        raise ValueError("ev_009 does not match the verified final hit")
    if (
        terminal_bounce["type"] != "bounce"
        or int(terminal_bounce["frame_start"]) != 463
        or int(terminal_bounce["frame_end"]) != 463
    ):
        raise ValueError("ev_010 does not match the verified terminal bounce")
    return final_hit, terminal_bounce


def _review_frames(
    video_path: Path,
    manifest: ClipManifest,
    timestamps: Sequence[float],
) -> Iterator[CanonicalFrame]:
    for record in iter_canonical_frames(video_path, manifest, timestamps=timestamps):
        if REVIEW_START_FRAME <= record.frame_id <= REVIEW_END_FRAME:
            yield CanonicalFrame(
                frame_id=record.frame_id - REVIEW_START_FRAME,
                timestamp_seconds=record.timestamp_seconds,
                image_bgr=record.image_bgr,
            )


def render_terminal_bounce_review(
    video_path: Path,
    manifest: ClipManifest,
    timestamps: Sequence[float],
    events_path: Path,
    output_path: Path,
    *,
    tracking_path: Path | None = None,
) -> dict[str, object]:
    """Render a short VFR clip that includes both the final hit and terminal bounce."""
    events = load_event_rows(events_path)
    final_hit, terminal_bounce = _terminal_events(events)
    tracking = _load_optional_tracking(tracking_path)
    expected_frames = REVIEW_END_FRAME - REVIEW_START_FRAME + 1

    def draw(record: CanonicalFrame) -> np.ndarray:
        original_frame_id = REVIEW_START_FRAME + record.frame_id
        image = draw_events_frame(
            record.image_bgr,
            frame_id=original_frame_id,
            timestamp_seconds=float(timestamps[original_frame_id]),
            events=events,
        )
        point = tracking.get(original_frame_id)
        if point is not None:
            cv2.circle(
                image,
                (int(round(point[0])), int(round(point[1]))),
                13,
                (255, 255, 255),
                2,
            )
        banner = None
        color = (255, 255, 255)
        if int(final_hit["frame_start"]) <= original_frame_id <= int(final_hit["frame_end"]):
            banner = "ULTIMO GOLPE | ev_009"
            color = (0, 210, 255)
        if (
            int(terminal_bounce["frame_start"])
            <= original_frame_id
            <= int(terminal_bounce["frame_end"])
        ):
            banner = "BOTE TERMINAL | ev_010"
            color = (255, 130, 40)
        if banner:
            height, width = image.shape[:2]
            cv2.rectangle(image, (18, height - 96), (width - 18, height - 20), (0, 0, 0), -1)
            cv2.rectangle(image, (18, height - 96), (width - 18, height - 20), color, 4)
            cv2.putText(
                image,
                banner,
                (42, height - 45),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.25,
                color,
                3,
                cv2.LINE_AA,
            )
        return image

    metadata = render_canonical_vfr_overlay(
        _review_frames(video_path, manifest, timestamps),
        output_path,
        draw,
        expected_frames=expected_frames,
        expected_width=manifest.canonical_width,
        expected_height=manifest.canonical_height,
    )
    return {
        "mode": "canonical_vfr",
        "source_frame_start": REVIEW_START_FRAME,
        "source_frame_end": REVIEW_END_FRAME,
        "includes_final_hit": True,
        "includes_terminal_bounce": True,
        "tracking_available": bool(tracking),
        **metadata,
    }


def _contact_panel(
    image: np.ndarray,
    *,
    frame_id: int,
    timestamp: float,
) -> np.ndarray:
    width, height = 600, 376
    resized = cv2.resize(image, (width, 336), interpolation=cv2.INTER_AREA)
    panel = np.zeros((height, width, 3), dtype=np.uint8)
    panel[:336] = resized
    terminal = frame_id == 463
    color = (0, 255, 255) if terminal else (220, 220, 220)
    thickness = 8 if terminal else 2
    cv2.rectangle(panel, (0, 0), (width - 1, height - 1), color, thickness)
    cv2.rectangle(panel, (0, 0), (width, 42), (0, 0, 0), -1)
    title = f"FRAME {frame_id} | {timestamp:.6f} s"
    if terminal:
        title += " | BOTE TERMINAL"
    cv2.putText(
        panel,
        title,
        (12, 29),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        color,
        2,
        cv2.LINE_AA,
    )
    return panel


def render_terminal_bounce_contact_sheet(
    video_path: Path,
    manifest: ClipManifest,
    timestamps: Sequence[float],
    events_path: Path,
    output_path: Path,
) -> dict[str, object]:
    """Render frames 459–467 and emphasize the verified bounce at frame 463."""
    events = load_event_rows(events_path)
    _final_hit, terminal_bounce = _terminal_events(events)
    if float(terminal_bounce["time_start_seconds"]) != float(timestamps[463]):
        raise ValueError("ev_010 timestamp does not match frame 463")
    selected = {
        record.frame_id: record.image_bgr
        for record in iter_canonical_frames(video_path, manifest, timestamps=timestamps)
        if record.frame_id in CONTACT_FRAME_IDS
    }
    if set(selected) != set(CONTACT_FRAME_IDS):
        raise RuntimeError("Could not decode all terminal-bounce contact frames")
    panels = [
        _contact_panel(
            selected[frame_id],
            frame_id=frame_id,
            timestamp=float(timestamps[frame_id]),
        )
        for frame_id in CONTACT_FRAME_IDS
    ]
    sheet = np.vstack([np.hstack(panels[index : index + 3]) for index in range(0, 9, 3)])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), sheet):
        raise RuntimeError(f"Could not write terminal-bounce contact sheet: {output_path}")
    return {
        "path": str(output_path),
        "frames": list(CONTACT_FRAME_IDS),
        "terminal_frame": 463,
        "event_id": "ev_010",
        "width": int(sheet.shape[1]),
        "height": int(sheet.shape[0]),
        "canonical_source": True,
    }
