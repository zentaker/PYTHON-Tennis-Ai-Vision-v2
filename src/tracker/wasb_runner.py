"""Orientation-safe, multi-clip WASB runner for external Stage 2 execution."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import cv2
import numpy as np

from src.project.clip_manifest import ClipManifest
from src.video.canonical_frames import CanonicalFrame, iter_canonical_frames
from src.video.vfr_overlay import render_canonical_vfr_overlay


INPUT_WIDTH = 512
INPUT_HEIGHT = 288
FRAMES_IN = 3
CENTER_CHANNEL = 1
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)
CSV_COLUMNS = [
    "frame_id",
    "timestamp_seconds",
    "x_pixel",
    "y_pixel",
    "confidence",
    "detected",
    "canonical_width",
    "canonical_height",
]


class Predictor(Protocol):
    """Lightweight interface implemented by the real WASB model and test doubles."""

    def __call__(self, frames_bgr: Sequence[np.ndarray]) -> tuple[float, float, float]: ...


@dataclass(frozen=True)
class Detection:
    """One prediction expressed in canonical pixel coordinates."""

    frame_id: int
    timestamp_seconds: float
    x_pixel: float
    y_pixel: float
    confidence: float
    detected: bool
    canonical_width: int
    canonical_height: int


class WasbPredictor:
    """Heavy WASB adapter; instantiated only by the real external CLI."""

    def __init__(
        self,
        model: Any,
        device: Any,
        torch_module: Any,
        get_transform: Any,
        affine_transform: Any,
    ) -> None:
        self.model = model
        self.device = device
        self.torch = torch_module
        self.get_transform = get_transform
        self.affine_transform = affine_transform

    def _preprocess_frame(self, frame_bgr: np.ndarray) -> tuple[Any, np.ndarray]:
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        trans_input = self.get_transform(frame_rgb, (INPUT_WIDTH, INPUT_HEIGHT))
        trans_output_inv = self.get_transform(
            frame_rgb,
            (INPUT_WIDTH, INPUT_HEIGHT),
            inv=1,
        )
        warped = cv2.warpAffine(
            frame_rgb,
            trans_input,
            (INPUT_WIDTH, INPUT_HEIGHT),
            flags=cv2.INTER_LINEAR,
        )
        image = warped.astype(np.float32) / 255.0
        image = image.transpose(2, 0, 1)
        image = (image - IMAGENET_MEAN) / IMAGENET_STD
        return self.torch.from_numpy(image), trans_output_inv

    def __call__(self, frames_bgr: Sequence[np.ndarray]) -> tuple[float, float, float]:
        tensors = []
        inverse_transform = None
        for frame in frames_bgr:
            tensor, inverse_transform = self._preprocess_frame(frame)
            tensors.append(tensor)
        input_tensor = self.torch.cat(tensors, dim=0).unsqueeze(0).to(self.device)
        with self.torch.inference_mode():
            heatmaps = self.model(input_tensor)[0].sigmoid().detach().cpu().numpy()[0]
        heatmap = heatmaps[CENTER_CHANNEL]
        flat_index = int(np.argmax(heatmap))
        y_heat, x_heat = np.unravel_index(flat_index, heatmap.shape)
        xy = self.affine_transform(
            np.array([float(x_heat), float(y_heat)], dtype=np.float32),
            inverse_transform,
        )
        return float(xy[0]), float(xy[1]), float(heatmap[y_heat, x_heat])


def load_wasb_predictor(
    checkpoint_path: Path,
    wasb_root: Path,
    device_name: str,
) -> WasbPredictor:
    """Import PyTorch/WASB lazily and load the requested checkpoint."""
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"WASB checkpoint not found: {checkpoint_path}")
    wasb_src = wasb_root / "src"
    if not wasb_src.is_dir():
        raise FileNotFoundError(f"WASB source tree not found: {wasb_src}")
    if str(wasb_src) not in sys.path:
        sys.path.insert(0, str(wasb_src))

    try:
        import torch
        from omegaconf import OmegaConf

        from dataloaders.dataset_loader import get_transform
        from models import build_model
        from utils.image import affine_transform
    except ImportError as exc:
        raise RuntimeError(
            "Tracker dependencies are unavailable. Install the tracker extra on Linux/WSL/GPU."
        ) from exc

    if device_name == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device_name)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is False")

    model_cfg = OmegaConf.load(wasb_src / "configs" / "model" / "wasb.yaml")
    cfg = OmegaConf.create({"model": model_cfg})
    model = build_model(cfg)
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()
    return WasbPredictor(model, device, torch, get_transform, affine_transform)


def _centered_windows(
    frames: Iterable[CanonicalFrame],
) -> Iterable[tuple[CanonicalFrame, list[np.ndarray]]]:
    """Yield one three-frame predictor window for every logical input frame."""
    iterator = iter(frames)
    try:
        current = next(iterator)
    except StopIteration as exc:
        raise ValueError("No canonical frames were decoded") from exc

    buffer: deque[np.ndarray] = deque(
        [current.image_bgr.copy(), current.image_bgr.copy()],
        maxlen=FRAMES_IN,
    )
    while True:
        try:
            following = next(iterator)
        except StopIteration:
            following = None
        next_image = current.image_bgr if following is None else following.image_bgr
        buffer.append(next_image.copy())
        yield current, list(buffer)
        if following is None:
            break
        current = following


def validate_detection(
    detection: Detection,
    confidence_threshold: float,
) -> None:
    """Reject invalid high-confidence predictions instead of emitting bad coordinates."""
    if not np.isfinite(detection.confidence) or not 0.0 <= detection.confidence <= 1.0:
        raise ValueError(f"Invalid confidence at frame {detection.frame_id}")
    if detection.confidence < confidence_threshold:
        return
    if not np.isfinite(detection.x_pixel) or not np.isfinite(detection.y_pixel):
        raise ValueError(f"Non-finite detected point at frame {detection.frame_id}")
    if not (
        0 <= detection.x_pixel < detection.canonical_width
        and 0 <= detection.y_pixel < detection.canonical_height
    ):
        raise ValueError(f"Detected point outside canonical bounds at frame {detection.frame_id}")


def infer_canonical_frames(
    frames: Iterable[CanonicalFrame],
    predictor: Predictor,
    output_csv: Path,
    *,
    confidence_threshold: float,
    expected_frames: int,
    canonical_width: int,
    canonical_height: int,
) -> dict[str, float]:
    """Predict exactly once per canonical frame and write the Stage 2 CSV."""
    if not 0.0 <= confidence_threshold <= 1.0:
        raise ValueError("confidence_threshold must be between 0 and 1")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    processed = 0
    detected_count = 0
    confidence_sum = 0.0
    confidences: list[float] = []
    started_at = time.perf_counter()

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for record, window in _centered_windows(frames):
            if record.frame_id != processed:
                raise ValueError(
                    f"Non-sequential frame_id: expected {processed}, got {record.frame_id}"
                )
            if record.image_bgr.shape[:2] != (canonical_height, canonical_width):
                raise ValueError(
                    f"Frame {record.frame_id} is not canonical: {record.image_bgr.shape[:2]}"
                )
            x_pixel, y_pixel, confidence = predictor(window)
            detected = bool(confidence >= confidence_threshold)
            detection = Detection(
                frame_id=record.frame_id,
                timestamp_seconds=record.timestamp_seconds,
                x_pixel=float(x_pixel),
                y_pixel=float(y_pixel),
                confidence=float(confidence),
                detected=detected,
                canonical_width=canonical_width,
                canonical_height=canonical_height,
            )
            validate_detection(detection, confidence_threshold)
            writer.writerow(
                {
                    "frame_id": detection.frame_id,
                    "timestamp_seconds": f"{detection.timestamp_seconds:.9f}",
                    "x_pixel": f"{detection.x_pixel:.3f}",
                    "y_pixel": f"{detection.y_pixel:.3f}",
                    "confidence": f"{detection.confidence:.6f}",
                    "detected": str(detection.detected).lower(),
                    "canonical_width": canonical_width,
                    "canonical_height": canonical_height,
                }
            )
            processed += 1
            detected_count += int(detected)
            confidence_sum += confidence
            confidences.append(float(confidence))

    if processed != expected_frames:
        raise ValueError(f"Expected {expected_frames} CSV rows, wrote {processed}")
    elapsed = time.perf_counter() - started_at
    return {
        "expected_frames": float(expected_frames),
        "processed_frames": float(processed),
        "detected_frames": float(detected_count),
        "detection_rate": detected_count / processed if processed else 0.0,
        "mean_confidence": confidence_sum / processed if processed else 0.0,
        "median_confidence": float(np.median(confidences)) if confidences else 0.0,
        "elapsed_seconds": elapsed,
        "inference_fps": processed / elapsed if elapsed else 0.0,
    }


def build_inference_report(
    metrics: dict[str, float],
    detections: Sequence[Detection],
    manifest: ClipManifest,
    *,
    device: str,
    pytorch_version: str,
    cuda_version: str | None,
    output_csv: Path,
    output_overlay: Path,
    total_elapsed_seconds: float,
) -> dict[str, object]:
    """Build the external execution report without requiring heavy imports."""
    frame_ids = [detection.frame_id for detection in detections]
    timestamps = [detection.timestamp_seconds for detection in detections]
    sequential_ids = frame_ids == list(range(manifest.frames_total))
    timestamps_monotonic = all(
        current > previous for previous, current in zip(timestamps, timestamps[1:])
    )
    canonical_dimensions_valid = all(
        detection.canonical_width == manifest.canonical_width
        and detection.canonical_height == manifest.canonical_height
        for detection in detections
    )
    detected_bounds_valid = all(
        not detection.detected
        or (
            0 <= detection.x_pixel < manifest.canonical_width
            and 0 <= detection.y_pixel < manifest.canonical_height
        )
        for detection in detections
    )
    processed_frames = int(metrics["processed_frames"])
    if processed_frames != manifest.frames_total or len(detections) != manifest.frames_total:
        raise ValueError("Inference report frame count does not match manifest")
    if not sequential_ids or not timestamps_monotonic:
        raise ValueError("Inference report frame IDs or timestamps are invalid")
    if not canonical_dimensions_valid or not detected_bounds_valid:
        raise ValueError("Inference report contains non-canonical detections")

    return {
        "status": "COMPLETED_PENDING_HUMAN_GATE",
        "clip_id": manifest.clip_id,
        "frames_expected": manifest.frames_total,
        "frames_processed": processed_frames,
        "detections": int(metrics["detected_frames"]),
        "detection_rate": metrics["detection_rate"],
        "confidence_mean": metrics["mean_confidence"],
        "confidence_median": metrics["median_confidence"],
        "inference_elapsed_seconds": metrics["elapsed_seconds"],
        "total_elapsed_seconds": total_elapsed_seconds,
        "inference_fps": metrics["inference_fps"],
        "device": device,
        "pytorch_version": pytorch_version,
        "cuda_version": cuda_version,
        "canonical_dimensions": {
            "width": manifest.canonical_width,
            "height": manifest.canonical_height,
        },
        "timestamp_verification": {
            "count": len(timestamps),
            "monotonic": timestamps_monotonic,
            "range_seconds": [timestamps[0], timestamps[-1]],
            "frame_ids_sequential": sequential_ids,
        },
        "bounds_verification": {
            "canonical_dimensions_valid": canonical_dimensions_valid,
            "detected_points_in_bounds": detected_bounds_valid,
        },
        "outputs": {
            "csv": str(output_csv),
            "overlay": str(output_overlay),
        },
    }


def write_inference_report(output_path: Path, report: dict[str, object]) -> None:
    """Persist the completed external inference report as JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_detection_csv(path: Path) -> list[Detection]:
    """Read and validate the orientation-aware Stage 2 CSV."""
    rows: list[Detection] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [name for name in CSV_COLUMNS if name not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Missing detection CSV columns: {missing}")
        for row in reader:
            rows.append(
                Detection(
                    frame_id=int(row["frame_id"]),
                    timestamp_seconds=float(row["timestamp_seconds"]),
                    x_pixel=float(row["x_pixel"]),
                    y_pixel=float(row["y_pixel"]),
                    confidence=float(row["confidence"]),
                    detected=row["detected"].lower() == "true",
                    canonical_width=int(row["canonical_width"]),
                    canonical_height=int(row["canonical_height"]),
                )
            )
    return rows


def draw_detection(frame_bgr: np.ndarray, detection: Detection) -> np.ndarray:
    """Draw one canonical-space detection without changing frame orientation."""
    output = frame_bgr.copy()
    if output.shape[:2] != (detection.canonical_height, detection.canonical_width):
        raise ValueError("Overlay frame dimensions do not match detection canonical space")
    if detection.detected:
        cv2.circle(
            output,
            (int(round(detection.x_pixel)), int(round(detection.y_pixel))),
            8,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )
    cv2.putText(
        output,
        f"frame {detection.frame_id} | t={detection.timestamp_seconds:.3f}s",
        (24, 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return output


def render_vfr_overlay(
    video_path: Path,
    manifest: ClipManifest,
    detections_csv: Path,
    output_overlay: Path,
    *,
    ffmpeg_binary: str = "ffmpeg",
) -> None:
    """Render canonical PNG frames and encode a timestamp-driven VFR review overlay."""
    detections = read_detection_csv(detections_csv)
    if len(detections) != manifest.frames_total:
        raise ValueError(
            f"Expected {manifest.frames_total} detections for overlay, found {len(detections)}"
        )
    detections_by_frame = {item.frame_id: item for item in detections}

    def render(record: CanonicalFrame) -> np.ndarray:
        detection = detections_by_frame.get(record.frame_id)
        if detection is None:
            raise ValueError("Detection/frame ID mismatch while rendering overlay")
        if not np.isclose(
            record.timestamp_seconds,
            detection.timestamp_seconds,
            rtol=0.0,
            atol=5e-10,
        ):
            raise ValueError("Detection/frame timestamp mismatch while rendering overlay")
        return draw_detection(record.image_bgr, detection)

    render_canonical_vfr_overlay(
        iter_canonical_frames(video_path, manifest),
        output_overlay,
        render,
        expected_frames=manifest.frames_total,
        expected_width=manifest.canonical_width,
        expected_height=manifest.canonical_height,
        ffmpeg_binary=ffmpeg_binary,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--wasb-root", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-overlay", type=Path, required=True)
    parser.add_argument("--output-report", type=Path)
    parser.add_argument("--confidence-threshold", type=float, default=0.5)
    parser.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = ClipManifest.read(args.manifest)
    if args.video.suffix.lower() not in {".mp4", ".mov"}:
        raise ValueError(f"Unsupported video extension: {args.video.suffix}")
    output_report = args.output_report or args.output_overlay.with_name("inference_report.json")
    pipeline_started_at = time.perf_counter()
    predictor = load_wasb_predictor(args.checkpoint, args.wasb_root, args.device)
    metrics = infer_canonical_frames(
        iter_canonical_frames(args.video, manifest),
        predictor,
        args.output_csv,
        confidence_threshold=args.confidence_threshold,
        expected_frames=manifest.frames_total,
        canonical_width=manifest.canonical_width,
        canonical_height=manifest.canonical_height,
    )
    render_vfr_overlay(args.video, manifest, args.output_csv, args.output_overlay)
    detections = read_detection_csv(args.output_csv)
    report = build_inference_report(
        metrics,
        detections,
        manifest,
        device=str(predictor.device),
        pytorch_version=str(predictor.torch.__version__),
        cuda_version=(
            str(predictor.torch.version.cuda)
            if predictor.torch.version.cuda is not None
            else None
        ),
        output_csv=args.output_csv,
        output_overlay=args.output_overlay,
        total_elapsed_seconds=time.perf_counter() - pipeline_started_at,
    )
    write_inference_report(output_report, report)
    print(f"video={args.video}")
    print(f"manifest={args.manifest}")
    print(f"checkpoint={args.checkpoint}")
    print(f"wasb_root={args.wasb_root}")
    print(f"output_csv={args.output_csv}")
    print(f"output_overlay={args.output_overlay}")
    print(f"output_report={output_report}")
    for key, value in metrics.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
