"""Render Stage 1 court calibration evidence images."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

import cv2
import matplotlib.pyplot as plt
import numpy as np

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.court.coordinates import COURT_DIMENSIONS
from src.court.homography import apply_homography


def court_line_segments() -> list[tuple[str, tuple[float, float], tuple[float, float]]]:
    """Return known court line segments in court coordinates."""
    dims = COURT_DIMENSIONS
    d = dims.doubles_half_width_m
    s = dims.singles_half_width_m
    b = dims.half_length_m
    service = dims.service_line_distance_m
    center_mark_len = 0.10

    return [
        ("far_baseline", (-d, b), (d, b)),
        ("near_baseline", (-d, -b), (d, -b)),
        ("left_doubles_sideline", (-d, -b), (-d, b)),
        ("right_doubles_sideline", (d, -b), (d, b)),
        ("left_singles_sideline", (-s, -b), (-s, b)),
        ("right_singles_sideline", (s, -b), (s, b)),
        ("far_service_line", (-s, service), (s, service)),
        ("near_service_line", (-s, -service), (s, -service)),
        ("center_service_far", (0.0, 0.0), (0.0, service)),
        ("center_service_near", (0.0, 0.0), (0.0, -service)),
        ("net_left_half", (-d, 0.0), (0.0, 0.0)),
        ("net_right_half", (0.0, 0.0), (d, 0.0)),
        ("far_center_mark", (0.0, b), (0.0, b - center_mark_len)),
        ("near_center_mark", (0.0, -b), (0.0, -b + center_mark_len)),
    ]


def sample_segment(
    start: tuple[float, float],
    end: tuple[float, float],
    samples: int = 100,
) -> np.ndarray:
    """Sample a court line segment into Nx2 points."""
    start_arr = np.array(start, dtype=np.float64)
    end_arr = np.array(end, dtype=np.float64)
    alpha = np.linspace(0.0, 1.0, samples, dtype=np.float64)[:, None]
    return start_arr * (1.0 - alpha) + end_arr * alpha


def render_court_2d_top(output_path: Path) -> None:
    """Render an empty 2D top view of the tennis court."""
    dims = COURT_DIMENSIONS
    margin = 1.25
    fig, ax = plt.subplots(figsize=(7.2, 12.0), dpi=180)
    ax.set_facecolor("#f6f2e8")
    fig.patch.set_facecolor("#f6f2e8")

    for name, start, end in court_line_segments():
        width = 2.4 if "net" not in name else 3.2
        color = "#111111" if "net" not in name else "#007c89"
        ax.plot([start[0], end[0]], [start[1], end[1]], color=color, linewidth=width)

    ax.annotate(
        "11.885 m",
        xy=(dims.doubles_half_width_m + 0.35, 0),
        xytext=(dims.doubles_half_width_m + 0.75, 0),
        rotation=90,
        va="center",
        ha="center",
        fontsize=9,
        arrowprops={"arrowstyle": "<->", "color": "#333333"},
    )
    ax.annotate(
        "10.97 m",
        xy=(0, -dims.half_length_m - 0.45),
        xytext=(0, -dims.half_length_m - 0.95),
        va="center",
        ha="center",
        fontsize=9,
        arrowprops={"arrowstyle": "<->", "color": "#333333"},
    )
    ax.text(0, 0.25, "net", ha="center", va="bottom", fontsize=9, color="#007c89")
    ax.set_xlim(-dims.doubles_half_width_m - margin, dims.doubles_half_width_m + margin)
    ax.set_ylim(-dims.half_length_m - margin, dims.half_length_m + margin)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("X meters")
    ax.set_ylabel("Y meters")
    ax.grid(color="#dddddd", linewidth=0.5)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def draw_polyline(
    image: np.ndarray,
    points: Iterable[tuple[float, float]],
    color: tuple[int, int, int],
    thickness: int = 3,
) -> None:
    """Draw a projected polyline if it has enough in-frame points."""
    array = np.array(list(points), dtype=np.float64)
    if array.size == 0:
        return
    rounded = np.round(array).astype(np.int32)
    cv2.polylines(image, [rounded], isClosed=False, color=color, thickness=thickness, lineType=cv2.LINE_AA)


def render_reprojected_court_on_frame(
    frame_path: Path,
    homography_path: Path,
    output_path: Path,
) -> None:
    """Render known court lines reprojected from court coordinates onto the reference frame."""
    frame = cv2.imread(str(frame_path))
    if frame is None:
        raise FileNotFoundError(f"Could not open frame: {frame_path}")
    payload = json.loads(homography_path.read_text(encoding="utf-8"))
    inverse_h = np.linalg.inv(np.array(payload["H_pixel_to_court"], dtype=np.float64))

    overlay = frame.copy()
    for index, (_name, start, end) in enumerate(court_line_segments()):
        court_points = sample_segment(start, end, samples=140)
        pixel_points = apply_homography(inverse_h, court_points)
        color = (255, 255, 0) if index % 2 == 0 else (255, 0, 255)
        draw_polyline(overlay, pixel_points, color=color, thickness=3)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), overlay):
        raise RuntimeError(f"Could not write reprojected court image: {output_path}")


def render_all(
    frame_path: Path,
    homography_path: Path,
    top_output: Path,
    reprojected_output: Path,
) -> None:
    """Render both Stage 1 evidence images."""
    render_court_2d_top(top_output)
    render_reprojected_court_on_frame(frame_path, homography_path, reprojected_output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame", type=Path, default=Path("data/reference_clip/reference_frame.png"))
    parser.add_argument("--homography", type=Path, default=Path("data/reference_clip/homography.json"))
    parser.add_argument("--top-output", type=Path, default=Path("outputs/stage_1/court_2d_top.png"))
    parser.add_argument(
        "--reprojected-output",
        type=Path,
        default=Path("outputs/stage_1/reference_frame_with_reprojected_court.png"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    render_all(args.frame, args.homography, args.top_output, args.reprojected_output)
    print(f"Top view written to {args.top_output}")
    print(f"Reprojected court written to {args.reprojected_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
