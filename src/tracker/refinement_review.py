"""Generate local review assets for Stage 3 refinement."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_rows(path: Path) -> dict[int, dict]:
    rows = list(csv.DictReader(path.open("r", newline="", encoding="utf-8")))
    parsed = {}
    for row in rows:
        row["frame_id"] = int(row["frame_id"])
        row["confidence"] = float(row["confidence"])
        for key in ["x_raw", "y_raw", "x_smooth", "y_smooth"]:
            row[key] = float(row[key]) if row[key] else None
        parsed[row["frame_id"]] = row
    return parsed


def _unit_jumps(rows: dict[int, dict]) -> list[tuple[float, int, int, dict, dict]]:
    valid = [row for _, row in sorted(rows.items()) if row["x_smooth"] is not None and row["y_smooth"] is not None]
    jumps = []
    for previous, current in zip(valid, valid[1:]):
        gap = current["frame_id"] - previous["frame_id"]
        if gap != 1:
            continue
        distance = math.hypot(current["x_smooth"] - previous["x_smooth"], current["y_smooth"] - previous["y_smooth"])
        jumps.append((distance, previous["frame_id"], current["frame_id"], previous, current))
    return sorted(jumps, reverse=True)


def _accelerations(rows: dict[int, dict]) -> list[tuple[float, int, int, int, dict]]:
    valid = [row for _, row in sorted(rows.items()) if row["x_smooth"] is not None and row["y_smooth"] is not None]
    values = []
    for previous, current, following in zip(valid, valid[1:], valid[2:]):
        first_gap = current["frame_id"] - previous["frame_id"]
        second_gap = following["frame_id"] - current["frame_id"]
        if first_gap <= 0 or second_gap <= 0:
            continue
        first_velocity = (
            (current["x_smooth"] - previous["x_smooth"]) / first_gap,
            (current["y_smooth"] - previous["y_smooth"]) / first_gap,
        )
        second_velocity = (
            (following["x_smooth"] - current["x_smooth"]) / second_gap,
            (following["y_smooth"] - current["y_smooth"]) / second_gap,
        )
        acceleration = math.hypot(second_velocity[0] - first_velocity[0], second_velocity[1] - first_velocity[1])
        values.append((acceleration, current["frame_id"], previous["frame_id"], following["frame_id"], current))
    return sorted(values, reverse=True)


def _point(row: dict, prefix: str) -> tuple[int, int] | None:
    x_value = row.get(f"x_{prefix}")
    y_value = row.get(f"y_{prefix}")
    if x_value is None or y_value is None:
        return None
    return int(round(x_value)), int(round(y_value))


def _draw_panel(frame: np.ndarray, row: dict, title: str) -> np.ndarray:
    image = frame.copy()
    raw_point = _point(row, "raw")
    smooth_point = _point(row, "smooth")
    if raw_point is not None:
        cv2.circle(image, raw_point, 8, (0, 255, 255), 2)
        cv2.drawMarker(image, raw_point, (0, 255, 255), markerType=cv2.MARKER_CROSS, markerSize=18, thickness=2)
    if smooth_point is not None:
        color = (0, 0, 255)
        if row["source"] == "interpolated":
            color = (255, 0, 255)
        elif row["source"] == "rejected":
            color = (0, 165, 255)
        cv2.circle(image, smooth_point, 10, color, 3)

    cv2.rectangle(image, (0, 0), (image.shape[1], 95), (0, 0, 0), -1)
    label = f"{title} f={row['frame_id']} {row['source']} conf={row['confidence']:.3f}"
    cv2.putText(image, label, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(image, row["reason"] or "-", (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2, cv2.LINE_AA)
    return cv2.resize(image, (480, 270))


def generate_refinement_review(
    video_path: Path,
    before_csv: Path,
    after_csv: Path,
    output_dir: Path,
    *,
    focus_start: int | None = None,
    focus_end: int | None = None,
    excerpt_name: str = "refined_overlay_excerpt.mp4",
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    top_jump_dir = output_dir / "top_jump_frames"
    top_jump_dir.mkdir(parents=True, exist_ok=True)

    before = _load_rows(before_csv)
    after = _load_rows(after_csv)
    before_jumps = _unit_jumps(before)
    after_jumps = _unit_jumps(after)
    before_accelerations = _accelerations(before)

    new_rejections = [
        frame_id
        for frame_id, row in sorted(after.items())
        if row["source"] == "rejected" and before[frame_id]["source"] != "rejected"
    ]

    candidates = []
    for rank, (value, start, end, _previous, current) in enumerate(before_jumps[:10], 1):
        candidates.append(
            {
                "kind": "before_top_jump",
                "rank": rank,
                "frame_id": end,
                "from_frame": start,
                "to_frame": end,
                "value": f"{value:.6f}",
                "before_source": current["source"],
                "after_source": after[end]["source"],
                "before_reason": current["reason"],
                "after_reason": after[end]["reason"],
            }
        )
    for rank, (value, frame_id, previous, following, current) in enumerate(before_accelerations[:10], 1):
        candidates.append(
            {
                "kind": "before_top_accel",
                "rank": rank,
                "frame_id": frame_id,
                "from_frame": previous,
                "to_frame": following,
                "value": f"{value:.6f}",
                "before_source": current["source"],
                "after_source": after[frame_id]["source"],
                "before_reason": current["reason"],
                "after_reason": after[frame_id]["reason"],
            }
        )
    for frame_id in new_rejections:
        candidates.append(
            {
                "kind": "new_rejection",
                "rank": "",
                "frame_id": frame_id,
                "from_frame": frame_id - 1,
                "to_frame": frame_id + 1,
                "value": "",
                "before_source": before[frame_id]["source"],
                "after_source": after[frame_id]["source"],
                "before_reason": before[frame_id]["reason"],
                "after_reason": after[frame_id]["reason"],
            }
        )

    candidates_path = output_dir / "anomaly_candidates.csv"
    with candidates_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "kind",
            "rank",
            "frame_id",
            "from_frame",
            "to_frame",
            "value",
            "before_source",
            "after_source",
            "before_reason",
            "after_reason",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidates)

    if focus_start is not None and focus_end is not None:
        focus_path = output_dir / "second12_anomaly_window.csv"
        with focus_path.open("w", newline="", encoding="utf-8") as handle:
            fieldnames = [
                "frame_id",
                "before_source",
                "after_source",
                "before_x_smooth",
                "before_y_smooth",
                "after_x_smooth",
                "after_y_smooth",
                "x_raw",
                "y_raw",
                "confidence",
                "before_reason",
                "after_reason",
            ]
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for frame_id in range(focus_start, focus_end + 1):
                if frame_id not in before or frame_id not in after:
                    continue
                writer.writerow(
                    {
                        "frame_id": frame_id,
                        "before_source": before[frame_id]["source"],
                        "after_source": after[frame_id]["source"],
                        "before_x_smooth": before[frame_id]["x_smooth"],
                        "before_y_smooth": before[frame_id]["y_smooth"],
                        "after_x_smooth": after[frame_id]["x_smooth"],
                        "after_y_smooth": after[frame_id]["y_smooth"],
                        "x_raw": after[frame_id]["x_raw"],
                        "y_raw": after[frame_id]["y_raw"],
                        "confidence": after[frame_id]["confidence"],
                        "before_reason": before[frame_id]["reason"],
                        "after_reason": after[frame_id]["reason"],
                    }
                )

    interesting_frames = sorted(
        set(new_rejections + [329] + [end for _value, _start, end, _previous, _current in before_jumps[:6]])
    )

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    frames = {}
    for frame_id in interesting_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
        ok, frame = cap.read()
        if ok:
            frames[frame_id] = frame
    cap.release()

    sheet_rows = []
    for frame_id in interesting_frames:
        frame = frames.get(frame_id)
        if frame is None:
            continue
        base = cv2.resize(frame, (480, 270))
        cv2.putText(base, f"FRAME {frame_id}", (20, 42), cv2.FONT_HERSHEY_SIMPLEX, 1.05, (255, 255, 255), 2, cv2.LINE_AA)
        row_image = np.hstack([base, _draw_panel(frame, before[frame_id], "before"), _draw_panel(frame, after[frame_id], "after")])
        sheet_rows.append(row_image)
        cv2.imwrite(str(top_jump_dir / f"frame_{frame_id:04d}_before_after.png"), row_image)

    if sheet_rows:
        cv2.imwrite(str(output_dir / "before_after_contact_sheet.png"), np.vstack(sheet_rows))

    excerpt_frames = []
    excerpt_centers = sorted(set(new_rejections + [329]))
    if focus_start is not None and focus_end is not None:
        excerpt_centers = [frame_id for frame_id in excerpt_centers if focus_start <= frame_id <= focus_end]
        if not excerpt_centers:
            excerpt_centers = [(focus_start + focus_end) // 2]
    for center in excerpt_centers:
        excerpt_frames.extend(range(max(0, center - 12), center + 13))
    excerpt_frames = sorted(set(excerpt_frames))

    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    writer = cv2.VideoWriter(
        str(output_dir / excerpt_name),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (1440, 270),
    )
    for frame_id in excerpt_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
        ok, frame = cap.read()
        if not ok:
            continue
        writer.write(np.hstack([cv2.resize(frame, (480, 270)), _draw_panel(frame, before[frame_id], "before"), _draw_panel(frame, after[frame_id], "after")]))
    cap.release()
    writer.release()

    summary = {
        "new_rejections": new_rejections,
        "interesting_frames": interesting_frames,
        "before_max_unit_jump": before_jumps[0][0] if before_jumps else 0.0,
        "after_max_unit_jump": after_jumps[0][0] if after_jumps else 0.0,
        "candidates_csv": str(candidates_path),
        "focus_start": focus_start,
        "focus_end": focus_end,
        "excerpt": str(output_dir / excerpt_name),
    }
    (output_dir / "refinement_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate before/after review assets for Stage 3 refinement.")
    parser.add_argument("--video", type=Path, default=PROJECT_ROOT / "data" / "reference_clip" / "madrid_R1.mov")
    parser.add_argument("--before-csv", type=Path, default=PROJECT_ROOT / "outputs" / "stage_3" / "refinement_review" / "smoothed_trajectory_before.csv")
    parser.add_argument("--after-csv", type=Path, default=PROJECT_ROOT / "outputs" / "stage_3" / "smoothed_trajectory.csv")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "outputs" / "stage_3" / "refinement_review")
    parser.add_argument("--focus-start", type=int)
    parser.add_argument("--focus-end", type=int)
    parser.add_argument("--excerpt-name", default="refined_overlay_excerpt.mp4")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = generate_refinement_review(
        args.video,
        args.before_csv,
        args.after_csv,
        args.output_dir,
        focus_start=args.focus_start,
        focus_end=args.focus_end,
        excerpt_name=args.excerpt_name,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
