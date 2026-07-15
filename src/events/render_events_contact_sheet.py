"""Render one five-frame visual review row per normalized Stage 4 event."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.events.render_events_overlay import EVENT_COLORS, load_event_rows
from src.project.clip_manifest import ClipManifest
from src.video.canonical_frames import iter_canonical_frames
from src.video.frame_timestamps import FrameTimestampSidecar, validate_sidecar_against_manifest


PANEL_WIDTH = 360
PANEL_HEIGHT = 250


def event_review_frames(event: dict[str, Any], frame_count: int) -> list[tuple[str, int]]:
    """Choose the requested context frames without duplicating point-event imagery."""
    start = int(event["frame_start"])
    end = int(event["frame_end"])
    if start == end:
        candidates = [
            ("previous -2", start - 2),
            ("previous", start - 1),
            ("POINT EVENT", start),
            ("next", start + 1),
            ("next +2", start + 2),
        ]
    else:
        candidates = [
            ("previous", start - 1),
            ("START", start),
            ("MID", (start + end) // 2),
            ("END", end),
            ("next", end + 1),
        ]
    return [(role, min(max(frame_id, 0), frame_count - 1)) for role, frame_id in candidates]


def _panel(
    image: np.ndarray,
    *,
    role: str,
    frame_id: int,
    timestamp: float,
    event: dict[str, Any],
) -> np.ndarray:
    resized = cv2.resize(image, (PANEL_WIDTH, 202), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((PANEL_HEIGHT, PANEL_WIDTH, 3), dtype=np.uint8)
    canvas[:202] = resized
    color = EVENT_COLORS.get(str(event["type"]), EVENT_COLORS["unknown"])
    cv2.rectangle(canvas, (0, 0), (PANEL_WIDTH - 1, PANEL_HEIGHT - 1), color, 3)
    cv2.rectangle(canvas, (0, 0), (PANEL_WIDTH, 34), (0, 0, 0), -1)
    cv2.putText(
        canvas,
        f"{role} | FRAME {frame_id:03d} | {timestamp:.6f} s",
        (8, 23),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        f"{event['type']} | {event['player']}/{event['side']}",
        (8, 230),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        color,
        2,
        cv2.LINE_AA,
    )
    return canvas


def render_events_contact_sheet(
    video_path: Path,
    manifest: ClipManifest,
    timestamps: Sequence[float],
    events_path: Path,
    output_path: Path,
) -> dict[str, object]:
    """Render exact canonical context frames for every normalized event."""
    events = load_event_rows(events_path)
    if len(timestamps) != manifest.frames_total:
        raise ValueError("Timestamp count does not match manifest frames_total")
    selections = [event_review_frames(event, manifest.frames_total) for event in events]
    required_ids = {frame_id for selection in selections for _role, frame_id in selection}
    frames = {
        record.frame_id: record.image_bgr
        for record in iter_canonical_frames(video_path, manifest, timestamps=timestamps)
        if record.frame_id in required_ids
    }
    if set(frames) != required_ids:
        raise RuntimeError("Could not decode every contact-sheet review frame")

    header_height = 44
    rows: list[np.ndarray] = []
    sections: list[dict[str, object]] = []
    for event, selection in zip(events, selections, strict=True):
        header = np.zeros((header_height, PANEL_WIDTH * 5, 3), dtype=np.uint8)
        color = EVENT_COLORS.get(str(event["type"]), EVENT_COLORS["unknown"])
        title = (
            f"{event['id']} | {event['type']} | {event['player']}/{event['side']} | "
            f"frames {event['frame_start']}-{event['frame_end']}"
        )
        cv2.putText(
            header,
            title,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
            cv2.LINE_AA,
        )
        panels = [
            _panel(
                frames[frame_id],
                role=role,
                frame_id=frame_id,
                timestamp=float(timestamps[frame_id]),
                event=event,
            )
            for role, frame_id in selection
        ]
        rows.append(np.vstack([header, np.hstack(panels)]))
        sections.append(
            {
                "event_id": event["id"],
                "frames": [frame_id for _role, frame_id in selection],
                "roles": [role for role, _frame_id in selection],
            }
        )
    sheet = np.vstack(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), sheet):
        raise RuntimeError(f"Could not write contact sheet: {output_path}")
    return {
        "path": str(output_path),
        "event_sections": len(sections),
        "sections": sections,
        "width": int(sheet.shape[1]),
        "height": int(sheet.shape[0]),
        "canonical_source": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--frame-timestamps", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = ClipManifest.read(args.manifest)
    sidecar = FrameTimestampSidecar.read(args.frame_timestamps)
    validate_sidecar_against_manifest(sidecar, manifest)
    metadata = render_events_contact_sheet(
        args.video,
        manifest,
        [frame.timestamp_seconds for frame in sidecar.frames],
        args.events,
        args.output,
    )
    print(f"Event contact sheet written to {args.output}: {metadata}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
