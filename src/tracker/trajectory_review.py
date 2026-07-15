"""Create compact, non-decisional review material for a Stage 3 baseline."""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np

from src.project.clip_manifest import ClipManifest
from src.tracker.render_trajectory_overlay import draw_trajectory_frame
from src.video.canonical_frames import iter_canonical_frames


def _rank_speeds(rows: list[dict], prefix: str) -> list[int]:
    candidates = [
        row
        for row in rows
        if row.get(f"x_{prefix}") is not None and row.get(f"y_{prefix}") is not None
    ]
    ranked: list[tuple[float, int]] = []
    for previous, current in zip(candidates, candidates[1:]):
        frame_gap = current["frame_id"] - previous["frame_id"]
        if frame_gap <= 0:
            continue
        if current.get("timestamp_seconds") is not None:
            delta = current["timestamp_seconds"] - previous["timestamp_seconds"]
        else:
            delta = float(frame_gap)
        distance = math.hypot(
            current[f"x_{prefix}"] - previous[f"x_{prefix}"],
            current[f"y_{prefix}"] - previous[f"y_{prefix}"],
        )
        ranked.append((distance / delta, current["frame_id"]))
    return [frame_id for _speed, frame_id in sorted(ranked, reverse=True)]


def _gap_centers(rows: list[dict]) -> list[int]:
    gaps: list[tuple[int, int]] = []
    start = None
    for index in range(len(rows) + 1):
        missing = index < len(rows) and rows[index]["x_smooth"] is None
        if missing and start is None:
            start = index
        elif not missing and start is not None:
            gaps.append((index - start, (start + index - 1) // 2))
            start = None
    return [center for _length, center in sorted(gaps, reverse=True)]


def _review_selection(rows: list[dict], limit: int = 12) -> list[tuple[int, str]]:
    groups = [
        ("rejected", [row["frame_id"] for row in rows if row["source"] == "rejected"]),
        (
            "interpolated",
            [row["frame_id"] for row in rows if row["source"] == "interpolated"],
        ),
        ("largest_raw_speed", _rank_speeds(rows, "raw")),
        ("largest_smooth_speed", _rank_speeds(rows, "smooth")),
        ("long_missing_gap", _gap_centers(rows)),
        (
            "low_confidence",
            [row["frame_id"] for row in sorted(rows, key=lambda item: item["confidence"])],
        ),
    ]
    selected: list[tuple[int, str]] = []
    seen: set[int] = set()
    while len(selected) < limit:
        added = False
        for label, frame_ids in groups:
            while frame_ids and frame_ids[0] in seen:
                frame_ids.pop(0)
            if frame_ids:
                frame_id = frame_ids.pop(0)
                selected.append((frame_id, label))
                seen.add(frame_id)
                added = True
                if len(selected) == limit:
                    break
        if not added:
            break
    return selected


def generate_stage3_contact_sheet(
    video_path: Path,
    manifest: ClipManifest,
    timestamps: Sequence[float],
    rows: list[dict],
    output_path: Path,
) -> dict[str, object]:
    """Sample review categories without making or replacing a human visual decision."""
    selection = _review_selection(rows)
    selected_ids = {frame_id for frame_id, _label in selection}
    frames = {
        record.frame_id: record.image_bgr
        for record in iter_canonical_frames(video_path, manifest, timestamps=timestamps)
        if record.frame_id in selected_ids
    }
    rows_by_id = {row["frame_id"]: row for row in rows}
    panels: list[np.ndarray] = []
    for frame_id, category in selection:
        frame = frames.get(frame_id)
        if frame is None:
            continue
        panel = draw_trajectory_frame(
            frame,
            rows_by_id[frame_id],
            deque(maxlen=1),
            debug=True,
        )
        cv2.rectangle(panel, (0, 86), (panel.shape[1], 128), (0, 0, 0), -1)
        cv2.putText(
            panel,
            f"review sample: {category}",
            (24, 116),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        panels.append(cv2.resize(panel, (640, 358)))
    if not panels:
        raise RuntimeError("No contact-sheet review samples could be decoded")
    blank = np.zeros_like(panels[0])
    while len(panels) % 3:
        panels.append(blank.copy())
    sheet_rows = [np.hstack(panels[index : index + 3]) for index in range(0, len(panels), 3)]
    sheet = np.vstack(sheet_rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), sheet):
        raise RuntimeError(f"Could not write contact sheet: {output_path}")
    return {
        "path": str(output_path),
        "samples": [
            {"frame_id": frame_id, "category": category}
            for frame_id, category in selection
            if frame_id in frames
        ],
        "width": int(sheet.shape[1]),
        "height": int(sheet.shape[0]),
        "replaces_video_review": False,
    }
