"""Minimal WASB runner for the Stage 2 visual viability check."""

from __future__ import annotations

import argparse
import csv
import sys
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np
import torch
from omegaconf import OmegaConf


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WASB_ROOT = PROJECT_ROOT / "third_party" / "WASB-SBDT"
WASB_SRC = WASB_ROOT / "src"

if str(WASB_SRC) not in sys.path:
    sys.path.insert(0, str(WASB_SRC))

from dataloaders.dataset_loader import get_transform  # noqa: E402
from models import build_model  # noqa: E402
from utils.image import affine_transform  # noqa: E402


INPUT_WIDTH = 512
INPUT_HEIGHT = 288
FRAMES_IN = 3
CENTER_CHANNEL = 1
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)


def load_wasb_model(weights_path: Path, device: torch.device) -> torch.nn.Module:
    """Load the official WASB HRNet architecture and checkpoint."""
    if not weights_path.exists():
        raise FileNotFoundError(f"WASB weights not found: {weights_path}")
    if not WASB_SRC.exists():
        raise FileNotFoundError(f"WASB source tree not found: {WASB_SRC}")

    model_cfg = OmegaConf.load(WASB_SRC / "configs" / "model" / "wasb.yaml")
    cfg = OmegaConf.create({"model": model_cfg})
    model = build_model(cfg)
    checkpoint = torch.load(weights_path, map_location=device, weights_only=False)
    state_dict = checkpoint["model_state_dict"]
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    return model


def _preprocess_frame(frame_bgr: np.ndarray) -> tuple[torch.Tensor, np.ndarray]:
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    trans_input = get_transform(frame_rgb, (INPUT_WIDTH, INPUT_HEIGHT))
    trans_output_inv = get_transform(frame_rgb, (INPUT_WIDTH, INPUT_HEIGHT), inv=1)
    warped = cv2.warpAffine(frame_rgb, trans_input, (INPUT_WIDTH, INPUT_HEIGHT), flags=cv2.INTER_LINEAR)
    image = warped.astype(np.float32) / 255.0
    image = image.transpose(2, 0, 1)
    image = (image - IMAGENET_MEAN) / IMAGENET_STD
    return torch.from_numpy(image), trans_output_inv


def _detect_center_channel(
    model: torch.nn.Module,
    frames: list[np.ndarray],
    device: torch.device,
) -> tuple[float, float, float]:
    tensors = []
    inverse_transform = None
    for frame in frames:
        tensor, inverse_transform = _preprocess_frame(frame)
        tensors.append(tensor)

    input_tensor = torch.cat(tensors, dim=0).unsqueeze(0).to(device)
    with torch.inference_mode():
        heatmaps = model(input_tensor)[0].sigmoid().detach().cpu().numpy()[0]

    heatmap = heatmaps[CENTER_CHANNEL]
    flat_index = int(np.argmax(heatmap))
    y_heat, x_heat = np.unravel_index(flat_index, heatmap.shape)
    confidence = float(heatmap[y_heat, x_heat])
    xy = affine_transform(np.array([float(x_heat), float(y_heat)], dtype=np.float32), inverse_transform)
    return float(xy[0]), float(xy[1]), confidence


def infer_clip(
    video_path: Path,
    model: torch.nn.Module,
    device: torch.device,
    output_csv: Path,
) -> dict[str, float]:
    """Run sliding-window WASB inference and write per-frame detections."""
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    detections = 0
    confidence_sum = 0.0
    start = time.perf_counter()

    ok, first_frame = cap.read()
    if not ok:
        raise RuntimeError(f"Could not read first frame: {video_path}")

    frame_buffer: deque[np.ndarray] = deque([first_frame.copy(), first_frame.copy()], maxlen=FRAMES_IN)
    frame_id = 0

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["frame_id", "x_pixel", "y_pixel", "confidence"])
        writer.writeheader()

        current = first_frame
        while True:
            ok, next_frame = cap.read()
            if not ok:
                next_frame = current.copy()
                end_after_this = True
            else:
                end_after_this = False

            frame_buffer.append(next_frame.copy())
            x_pixel, y_pixel, confidence = _detect_center_channel(model, list(frame_buffer), device)
            writer.writerow(
                {
                    "frame_id": frame_id,
                    "x_pixel": f"{x_pixel:.3f}",
                    "y_pixel": f"{y_pixel:.3f}",
                    "confidence": f"{confidence:.6f}",
                }
            )
            if confidence >= 0.5:
                detections += 1
            confidence_sum += confidence

            frame_id += 1
            current = next_frame
            if end_after_this:
                break

    cap.release()
    elapsed = time.perf_counter() - start
    processed_frames = frame_id
    return {
        "total_frames": float(total_frames or processed_frames),
        "processed_frames": float(processed_frames),
        "detected_frames": float(detections),
        "detection_rate": detections / processed_frames if processed_frames else 0.0,
        "mean_confidence": confidence_sum / processed_frames if processed_frames else 0.0,
        "elapsed_seconds": elapsed,
        "fps": processed_frames / elapsed if elapsed else 0.0,
    }


def render_overlay(video_path: Path, detections_csv: Path, output_mp4: Path) -> None:
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    detections: dict[int, tuple[float, float, float]] = {}
    with detections_csv.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            detections[int(row["frame_id"])] = (
                float(row["x_pixel"]),
                float(row["y_pixel"]),
                float(row["confidence"]),
            )

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    writer = cv2.VideoWriter(str(output_mp4), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open output video writer: {output_mp4}")

    frame_id = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        detection = detections.get(frame_id)
        if detection is not None:
            x_pixel, y_pixel, confidence = detection
            if np.isfinite(x_pixel) and np.isfinite(y_pixel):
                color = (0, 0, 255) if confidence >= 0.5 else (0, 255, 255)
                cv2.circle(frame, (int(round(x_pixel)), int(round(y_pixel))), 8, color, 2)
        writer.write(frame)
        frame_id += 1

    cap.release()
    writer.release()

    check = cv2.VideoCapture(str(output_mp4))
    ok, _ = check.read()
    check.release()
    if not ok:
        raise RuntimeError(f"Overlay MP4 was written but could not be read: {output_mp4}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run WASB on a video and render detection overlay.")
    parser.add_argument("--video", type=Path, default=PROJECT_ROOT / "data" / "reference_clip" / "madrid_R1.mov")
    parser.add_argument("--weights", type=Path, default=PROJECT_ROOT / "models" / "wasb" / "wasb_tennis_best.pth.tar")
    parser.add_argument("--csv", type=Path, default=PROJECT_ROOT / "data" / "reference_clip" / "wasb_detections.csv")
    parser.add_argument("--overlay", type=Path, default=PROJECT_ROOT / "outputs" / "stage_2" / "wasb_detections_overlay.mp4")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is False")

    model = load_wasb_model(args.weights, device)
    metrics = infer_clip(args.video, model, device, args.csv)
    render_overlay(args.video, args.csv, args.overlay)
    print(f"device={device}")
    print(f"video={args.video}")
    print(f"weights={args.weights}")
    print(f"csv={args.csv}")
    print(f"overlay={args.overlay}")
    for key, value in metrics.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
