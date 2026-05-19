"""Generate an approximate visual guide for manual court calibration."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[2]))


GUIDE_POINTS_APPROX: dict[int, tuple[str, tuple[int, int]]] = {
    1: ("far_left", (610, 279)),
    2: ("far_right", (1301, 279)),
    3: ("near_left", (378, 772)),
    4: ("near_right", (1535, 772)),
    5: ("far_left_service", (686, 354)),
    6: ("far_right_service", (1228, 354)),
    7: ("near_left_service", (516, 604)),
    8: ("near_right_service", (1390, 604)),
}


def draw_calibration_guide(image: np.ndarray) -> np.ndarray:
    """Draw approximate numbered markers that explain the requested click order."""
    guide = image.copy()
    for index, (label, (x, y)) in GUIDE_POINTS_APPROX.items():
        cv2.circle(guide, (x, y), 16, (0, 255, 255), -1)
        cv2.circle(guide, (x, y), 18, (0, 0, 0), 3)
        cv2.putText(
            guide,
            str(index),
            (x - 7, y + 7),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            guide,
            label,
            (x + 22, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )
    return guide


def generate_calibration_guide(image_path: Path, output_path: Path) -> None:
    """Load a reference image and save an approximate calibration guide."""
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Could not open image: {image_path}")
    guide = draw_calibration_guide(image)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), guide):
        raise RuntimeError(f"Could not write guide image: {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, default=Path("data/reference_clip/reference_frame.png"))
    parser.add_argument("--output", type=Path, default=Path("outputs/stage_1/calibration_guide.png"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generate_calibration_guide(args.image, args.output)
    print(f"Calibration guide saved to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
