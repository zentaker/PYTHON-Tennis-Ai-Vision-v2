"""Interactive court calibration by clicking known court points on the reference frame."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.court.coordinates import CALIBRATION_POINT_ORDER, CalibrationLayout


def build_calibration_payload(
    points_pixel: dict[str, tuple[int, int]],
    image_path: Path,
    layout: CalibrationLayout,
) -> dict[str, object]:
    """Build the serializable payload for clicked calibration points."""
    missing = [name for name in CALIBRATION_POINT_ORDER if name not in points_pixel]
    if missing:
        raise ValueError(f"Missing calibration points: {', '.join(missing)}")

    return {
        "image_path": str(image_path),
        "layout": layout,
        "point_order": list(CALIBRATION_POINT_ORDER),
        "court_corners_pixel": {
            name: [int(points_pixel[name][0]), int(points_pixel[name][1])]
            for name in CALIBRATION_POINT_ORDER
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def draw_points(image: np.ndarray, points_pixel: dict[str, tuple[int, int]]) -> np.ndarray:
    """Return a copy of the image with clicked points drawn on top."""
    preview = image.copy()
    for index, name in enumerate(CALIBRATION_POINT_ORDER, start=1):
        if name not in points_pixel:
            continue
        x, y = points_pixel[name]
        cv2.circle(preview, (x, y), 7, (0, 255, 255), -1)
        cv2.circle(preview, (x, y), 9, (0, 0, 0), 2)
        cv2.putText(
            preview,
            f"{index}. {name}",
            (x + 10, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )
    return preview


def save_calibration_outputs(
    image: np.ndarray,
    points_pixel: dict[str, tuple[int, int]],
    image_path: Path,
    json_output: Path,
    preview_output: Path,
    layout: CalibrationLayout,
) -> None:
    """Persist clicked points as JSON and a preview image."""
    payload = build_calibration_payload(points_pixel, image_path, layout)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    preview_output.parent.mkdir(parents=True, exist_ok=True)
    preview = draw_points(image, points_pixel)
    if not cv2.imwrite(str(preview_output), preview):
        raise RuntimeError(f"Could not write preview image: {preview_output}")


def check_window(image_path: Path, duration_ms: int = 2000) -> None:
    """Open the reference frame briefly to verify WSLg/OpenCV window support."""
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Could not open image: {image_path}")
    window_name = "Stage 1 WSLg check"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.imshow(window_name, image)
    cv2.waitKey(duration_ms)
    cv2.destroyAllWindows()


def run_interactive(
    image_path: Path,
    json_output: Path,
    preview_output: Path,
    layout: CalibrationLayout,
) -> None:
    """Run the OpenCV mouse-click calibration flow."""
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Could not open image: {image_path}")

    points_pixel: dict[str, tuple[int, int]] = {}
    window_name = "Stage 1 court calibration"

    def current_index() -> int:
        return len(points_pixel)

    def current_point_name() -> str | None:
        index = current_index()
        if index >= len(CALIBRATION_POINT_ORDER):
            return None
        return CALIBRATION_POINT_ORDER[index]

    def render() -> np.ndarray:
        canvas = draw_points(image, points_pixel)
        point_name = current_point_name()
        if point_name is None:
            instruction = "All points captured. Press Enter to save, r to retry last, q to quit."
        else:
            instruction = f"Click: {point_name} | r=retry last | q=quit"
        cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 42), (0, 0, 0), -1)
        cv2.putText(
            canvas,
            instruction,
            (16, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        return canvas

    def on_mouse(event: int, x: int, y: int, _flags: int, _param: object) -> None:
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        point_name = current_point_name()
        if point_name is None:
            return
        points_pixel[point_name] = (int(x), int(y))
        cv2.imshow(window_name, render())

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window_name, on_mouse)
    cv2.imshow(window_name, render())

    while True:
        key = cv2.waitKey(50) & 0xFF
        if key in (ord("q"), 27):
            cv2.destroyAllWindows()
            raise RuntimeError("Calibration cancelled by user")
        if key == ord("r") and points_pixel:
            last_name = CALIBRATION_POINT_ORDER[len(points_pixel) - 1]
            points_pixel.pop(last_name, None)
            cv2.imshow(window_name, render())
        if key in (13, 10) and len(points_pixel) == len(CALIBRATION_POINT_ORDER):
            break

    cv2.destroyAllWindows()
    save_calibration_outputs(image, points_pixel, image_path, json_output, preview_output, layout)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, default=Path("data/reference_clip/reference_frame.png"))
    parser.add_argument("--output", type=Path, default=Path("data/reference_clip/court_corners_pixel.json"))
    parser.add_argument(
        "--preview",
        type=Path,
        default=Path("outputs/stage_1/calibration_clicks_preview.png"),
    )
    parser.add_argument("--layout", choices=("doubles", "singles"), default="doubles")
    parser.add_argument("--check-window", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check_window:
        check_window(args.image)
        print("OpenCV window check completed")
    else:
        run_interactive(args.image, args.output, args.preview, args.layout)
        print(f"Calibration points saved to {args.output}")
        print(f"Preview saved to {args.preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
