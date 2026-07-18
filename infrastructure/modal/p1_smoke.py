"""Guarded Modal adapter for the ten-frame P1 GPU smoke.

This module is intentionally the only place that knows about Modal. Importing it
without the optional ``modal`` package is safe and performs no network operation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.prepare_p1_modal_smoke_inputs import (
    DEFAULT_OUTPUT,
    prepare_package,
    verify_package,
)


ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "containers/player-perception/Dockerfile"
MODEL_BUNDLE = ROOT / "config/player_perception/p1_openmmlab.json"
PROVIDER_CONFIG = ROOT / "config/providers/modal_p1_smoke.json"
APPROVAL_FILE = ROOT / ".modal_smoke_approval.json"
CALL_RECORD_FILE = ROOT / ".modal_smoke_function_call.json"
OUTPUT_DIR = ROOT / "outputs/nivel_a2_01/stage_p1_modal_smoke"
GPU_FALLBACK = ["L4", "A10", "T4"]
run_smoke: Any = None
EXPECTED_OUTPUTS = (
    "player_tracks.csv",
    "player_pose.jsonl",
    "player_court_positions.csv",
    "contact_audit.json",
    "perception_report.json",
    "player_pose_overlay.mp4",
    "contact_audit_contact_sheet.png",
    "artifact_manifest.json",
    "modal_execution_report.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _validate_provider_config(config: dict[str, Any]) -> None:
    if config["gpu_allowlist"] != GPU_FALLBACK or config["gpu_fallback_order"] != GPU_FALLBACK:
        raise ValueError("Modal GPU fallback must be exactly L4, A10, T4")
    if config["max_execution_seconds"] > 900 or config["retries"] != 0:
        raise ValueError("Modal smoke exceeds the execution or retry guard")
    if config["max_frames"] != 10 or config["max_gpu_count"] != 1:
        raise ValueError("Modal smoke must request exactly ten frames and one GPU")
    if any(config[field] for field in ("deployed", "detached", "reservation")):
        raise ValueError("Modal smoke must remain ephemeral, attached and unreserved")
    if config["budget_status"] != "NOT_CONFIGURED" or config["authentication_status"] != "NOT_CONFIGURED":
        raise ValueError("Modal financial/authentication guards must start NOT_CONFIGURED")
    if config["subscription_cost_usd"] != 0 or config["included_monthly_credits_usd"] != 30:
        raise ValueError("Modal Starter static cost/credit declaration is invalid")
    if config["expected_charge_usd"] is not None or config["max_out_of_pocket_approved_usd"] != 0:
        raise ValueError("Modal smoke must not guarantee or approve a real charge")
    if config["pricing_status"] != "VERIFIED_STATIC" or not config["requires_free_credit"]:
        raise ValueError("Modal pricing/free-credit guards are invalid")


def _validate_approval(path: Path = APPROVAL_FILE) -> bool:
    if not path.is_file():
        return False
    approval = _load_json(path)
    required = (
        "modal_authenticated",
        "workspace_budget_confirmed",
        "free_credit_confirmed",
        "approved_for_one_smoke",
    )
    return all(approval.get(field) is True for field in required)


def _validate_core_is_provider_neutral() -> None:
    for path in (ROOT / "src/player_perception", ROOT / "src/video", ROOT / "src/project"):
        for source in path.rglob("*.py"):
            if re.search(r"^\s*(?:from|import)\s+modal\b", source.read_text(encoding="utf-8"), re.MULTILINE):
                raise ValueError(f"core imports Modal: {source}")


def _package_path(output_root: Path = DEFAULT_OUTPUT) -> Path:
    return output_root / "inputs/p1_smoke_manifest.json"


def _package_id(package_path: Path) -> str:
    return _sha256(package_path)


def validate_local_contract() -> dict[str, Any]:
    """Validate everything required before a future authenticated remote call."""
    if not DOCKERFILE.is_file():
        raise FileNotFoundError(DOCKERFILE)
    for required in (
        ROOT / "data/clips/nivel_a2_01/clip_manifest.json",
        ROOT / "data/clips/nivel_a2_01/homography.json",
        ROOT / "outputs/nivel_a2_01/stage_3/smoothed_trajectory.csv",
        ROOT / "outputs/nivel_a2_01/stage_4/events.json",
        MODEL_BUNDLE,
        PROVIDER_CONFIG,
    ):
        if not required.is_file():
            raise FileNotFoundError(required)
    bundle = _load_json(MODEL_BUNDLE)
    for component in ("detector", "pose"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(bundle[component]["checksum_sha256"])):
            raise ValueError(f"{component} checkpoint checksum is not pinned")
    config = _load_json(PROVIDER_CONFIG)
    _validate_provider_config(config)
    _validate_core_is_provider_neutral()
    package_path = _package_path()
    if not package_path.is_file():
        prepare_package(output_root=DEFAULT_OUTPUT)
    package = verify_package(package_path)
    if package["frame_count"] != 10:
        raise ValueError("Modal package must contain exactly ten frames")
    return {
        "dockerfile": str(DOCKERFILE.relative_to(ROOT)),
        "image_source": "modal.Image.from_dockerfile(DOCKERFILE, context_dir=ROOT)",
        "platform": "linux/amd64 via Modal worker",
        "frame_ids": package["frame_ids"],
        "expected_outputs": list(EXPECTED_OUTPUTS),
        "volumes": ["tennisai-p1-assets:/assets", "tennisai-p1-results:/results"],
        "gpu_fallback": GPU_FALLBACK,
        "timeout_seconds": 900,
        "retries": 0,
        "approval_configured": _validate_approval(),
    }


def dry_run() -> dict[str, Any]:
    contract = validate_local_contract()
    if contract["approval_configured"]:
        raise ValueError("dry-run refuses an approval file with all values true")
    return {
        "status": "READY_FOR_MODAL_AUTH",
        "remote_calls": 0,
        "spend_generated": 0,
        "financial_status": "NOT_CONFIGURED",
        **contract,
    }


def _ensure_checkpoint(section: dict[str, Any], assets_root: Path) -> Path:
    expected = section.get("checksum_sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise RuntimeError("checkpoint checksum is missing or invalid")
    destination = assets_root / "models" / section["checkpoint"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and _sha256(destination) == expected:
        return destination
    if destination.exists():
        destination.unlink()
    with urllib.request.urlopen(section["checkpoint_url"], timeout=300) as response, destination.open("wb") as handle:
        while block := response.read(1024 * 1024):
            handle.write(block)
    if _sha256(destination) != expected:
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"checkpoint checksum mismatch: {section['checkpoint']}")
    return destination


def _build_modal_app(modal_module: Any) -> Any:
    image = modal_module.Image.from_dockerfile(str(DOCKERFILE), context_dir=ROOT)
    assets = modal_module.Volume.from_name("tennisai-p1-assets", create_if_missing=True)
    results = modal_module.Volume.from_name("tennisai-p1-results", create_if_missing=True)
    app = modal_module.App("tennis-ai-p1-modal-smoke")

    @app.function(
        image=image,
        gpu=GPU_FALLBACK,
        volumes={"/assets": assets, "/results": results},
        single_use_containers=True,
        retries=0,
        timeout=900,
        serialized=True,
    )
    def run_smoke(package_id: str, run_slug: str) -> dict[str, Any]:
        import csv
        import json as remote_json
        import subprocess as remote_subprocess
        from pathlib import Path as RemotePath

        import cv2
        import torch
        import modal as remote_modal

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is mandatory for the Modal P1 smoke; refusing CPU fallback")

        from src.player_perception.backends.openmmlab_backend import OpenMMLabBackend
        from src.player_perception.court_projection import CourtProjector
        from src.player_perception.outputs import write_artifact_manifest, write_perception_outputs
        from src.player_perception.pipeline import PerceptionPipeline
        from src.player_perception.render import write_contact_sheet, write_pose_overlay
        from src.player_perception.schemas import FrameInput

        started = _utc_now()
        input_id = remote_modal.current_input_id()
        assets_root = RemotePath("/assets")
        bundle_path = RemotePath("/workspace/config/player_perception/p1_openmmlab.json")
        bundle = remote_json.loads(bundle_path.read_text(encoding="utf-8"))
        _ensure_checkpoint(bundle["detector"], assets_root)
        _ensure_checkpoint(bundle["pose"], assets_root)
        assets.commit()
        package = remote_json.loads((assets_root / "inputs/p1_smoke_manifest.json").read_text(encoding="utf-8"))
        if package.get("frame_count") != 10:
            raise RuntimeError("remote smoke package is not exactly ten frames")
        frame_inputs = []
        for record in package["frames"]:
            image_path = assets_root / "inputs" / record["path"]
            image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if image is None:
                raise RuntimeError(f"missing smoke frame: {image_path}")
            frame_inputs.append(FrameInput(record["frame_id"], record["timestamp_seconds"], image, record["width"], record["height"]))
        output_dir = RemotePath("/results") / run_slug
        output_dir.mkdir(parents=True, exist_ok=True)
        backend = OpenMMLabBackend(bundle_path, "/assets/models", "/opt/openmmlab", device="cuda")
        pipeline = PerceptionPipeline(backend, CourtProjector(assets_root / "homography.json"))
        report = pipeline.run(frame_inputs, clip_id=package["clip_id"], device="cuda")
        events = remote_json.loads((assets_root / "events.json").read_text(encoding="utf-8")).get("events", [])
        trajectory = {}
        with (assets_root / "trajectory.csv").open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                value_x = row.get("x_smooth") or row.get("x_raw")
                value_y = row.get("y_smooth") or row.get("y_raw")
                if value_x and value_y:
                    trajectory[int(row["frame_id"])] = (float(value_x), float(value_y))
        paths = write_perception_outputs(report, output_dir, events=events, trajectory=trajectory)
        paths["player_pose_overlay.mp4"] = write_pose_overlay(frame_inputs, report.frames, output_dir / "player_pose_overlay.mp4")
        paths["contact_audit_contact_sheet.png"] = write_contact_sheet(frame_inputs, report.frames, output_dir / "contact_audit_contact_sheet.png")
        gpu = remote_subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], check=True, capture_output=True, text=True).stdout.strip()
        pose_counts = [len(pose.keypoints) for frame in report.frames for pose in frame.poses]
        if not pose_counts:
            raise RuntimeError("Modal smoke produced no poses")
        expected_keypoints = int(bundle["pose"]["keypoint_count"])
        if any(count != expected_keypoints for count in pose_counts):
            raise RuntimeError(f"whole-body keypoint count mismatch: {pose_counts}")
        names_present = sorted({point.name for frame in report.frames for pose in frame.poses for point in pose.keypoints})
        required_names = {"left_wrist", "right_wrist", "left_ankle", "right_ankle", "left_heel", "right_heel", "left_big_toe", "right_big_toe"}
        missing_names = sorted(required_names.difference(names_present))
        if missing_names:
            raise RuntimeError(f"whole-body required keypoints missing: {missing_names}")
        detections_by_frame = {str(frame.frame_id): len(frame.detections) for frame in report.frames}
        tracks_by_frame = {str(frame.frame_id): len(frame.tracks) for frame in report.frames}
        poses_by_frame = {str(frame.frame_id): len(frame.poses) for frame in report.frames}
        frames_without_people = [frame_id for frame_id, count in detections_by_frame.items() if count == 0]
        frames_not_two_players = [frame_id for frame_id, count in tracks_by_frame.items() if count != 2]
        run_id = input_id
        execution = {
            "schema_version": "1.0",
            "app_run_identifier": run_id,
            "function_input_id": input_id,
            "run_slug": run_slug,
            "package_id": package_id,
            "started_utc": started,
            "ended_utc": _utc_now(),
            "gpu": gpu,
            "cuda": torch.version.cuda,
            "torch_cuda_available": bool(torch.cuda.is_available()),
            "torch_device_name": torch.cuda.get_device_name() if torch.cuda.is_available() else None,
            "compute_capability": list(torch.cuda.get_device_capability()) if torch.cuda.is_available() else None,
            "peak_vram_bytes": torch.cuda.max_memory_reserved(),
            "frames_processed": report.frame_count,
            "detections_by_frame": detections_by_frame,
            "tracks_by_frame": tracks_by_frame,
            "poses_by_frame": poses_by_frame,
            "frames_without_people": frames_without_people,
            "frames_not_two_players": frames_not_two_players,
            "poses_generated": len(pose_counts),
            "keypoint_count_min": min(pose_counts),
            "keypoint_count_max": max(pose_counts),
            "keypoint_count_distribution": {str(count): pose_counts.count(count) for count in sorted(set(pose_counts))},
            "keypoint_names_present": names_present,
            "keypoints_missing": missing_names,
            "warnings": ["visual precision requires human review", "SimpleIoUTracker is not ByteTrack"],
            "status": "COMPLETED",
        }
        execution_path = output_dir / "modal_execution_report.json"
        execution_path.write_text(remote_json.dumps(execution, indent=2) + "\n", encoding="utf-8")
        paths["modal_execution_report.json"] = execution_path
        paths["artifact_manifest.json"] = write_artifact_manifest(paths.values(), output_dir)
        execution["output_checksums"] = {name: _sha256(path) for name, path in paths.items() if name not in {"modal_execution_report.json", "artifact_manifest.json"}}
        execution_path.write_text(remote_json.dumps(execution, indent=2) + "\n", encoding="utf-8")
        paths["artifact_manifest.json"] = write_artifact_manifest(paths.values(), output_dir)
        results.commit()
        return execution

    globals()["run_smoke"] = run_smoke

    @app.local_entrypoint()
    def _local_entrypoint() -> None:
        print(json.dumps(run_authenticated(), indent=2))

    return app


def _upload_inputs(volume: Any, package_root: Path) -> None:
    package_path = package_root / "inputs/p1_smoke_manifest.json"
    package = verify_package(package_path)
    if package["frame_count"] != 10 or len(package["frames"]) != 10:
        raise ValueError("refusing to upload a package that is not exactly ten frames")
    with volume.batch_upload(force=True) as batch:
        batch.put_file(str(package_root / "inputs/p1_smoke_manifest.json"), "/inputs/p1_smoke_manifest.json")
        for frame in sorted((package_root / "inputs/frames").glob("*.jpg")):
            batch.put_file(str(frame), f"/inputs/frames/{frame.name}")
        for local, remote in (
            (ROOT / "data/clips/nivel_a2_01/clip_manifest.json", "/clip_manifest.json"),
            (ROOT / "data/clips/nivel_a2_01/homography.json", "/homography.json"),
            (ROOT / "outputs/nivel_a2_01/stage_3/smoothed_trajectory.csv", "/trajectory.csv"),
            (ROOT / "outputs/nivel_a2_01/stage_4/events.json", "/events.json"),
        ):
            batch.put_file(str(local), remote)


def _download_results(volume: Any, remote_prefix: str, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    entries = volume.listdir(remote_prefix, recursive=True)
    for entry in entries:
        remote_path = getattr(entry, "path", str(entry))
        if remote_path.endswith("/"):
            continue
        relative = remote_path.removeprefix(remote_prefix).lstrip("/")
        local_path = destination / relative
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with local_path.open("wb") as handle:
            for block in volume.read_file(remote_path):
                handle.write(block)


def _verify_downloaded_outputs(destination: Path) -> None:
    missing = [name for name in EXPECTED_OUTPUTS if not (destination / name).is_file()]
    if missing:
        raise RuntimeError(f"Modal output download is incomplete: {missing}")
    manifest = _load_json(destination / "artifact_manifest.json")
    for entry in manifest.get("artifacts", []):
        path = destination / entry["path"]
        if not path.is_file() or _sha256(path) != entry["sha256"]:
            raise RuntimeError(f"downloaded output checksum mismatch: {path}")


def run_authenticated() -> dict[str, Any]:
    if not _validate_approval():
        raise RuntimeError(".modal_smoke_approval.json must contain four true approvals")
    contract = validate_local_contract()
    try:
        import modal
    except ImportError as exc:
        raise RuntimeError("install/authenticate Modal only for the explicitly approved run") from exc
    assets = modal.Volume.from_name("tennisai-p1-assets", create_if_missing=True)
    results = modal.Volume.from_name("tennisai-p1-results", create_if_missing=True)
    package_path = _package_path()
    package_id = _package_id(package_path)
    run_slug = f"p1-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{package_id[:12]}"
    _upload_inputs(assets, DEFAULT_OUTPUT)
    assets.commit()
    global app
    if app is None:
        app = _build_modal_app(modal)
    # The call is deliberately unreachable without the approval file above.
    call = run_smoke.spawn(package_id, run_slug)
    function_call_id = call.object_id
    CALL_RECORD_FILE.write_text(json.dumps({"function_call_id": function_call_id, "run_slug": run_slug}, indent=2) + "\n", encoding="utf-8")
    try:
        result = call.get()
    except KeyboardInterrupt:
        call.cancel()
        print(f"Cancelled Modal FunctionCall {function_call_id}")
        raise
    except Exception:
        try:
            call.cancel()
        finally:
            print(f"Modal FunctionCall failed and cancellation was attempted: {function_call_id}")
        raise
    results.reload()
    _download_results(results, f"/{result['run_slug']}", OUTPUT_DIR)
    _verify_downloaded_outputs(OUTPUT_DIR)
    from scripts.validate_stage_p1_outputs import validate

    validate(OUTPUT_DIR, contract["frame_ids"])
    return result


try:
    import modal as _modal  # type: ignore[import-not-found]
except ImportError:
    app = None
else:
    app = _build_modal_app(_modal)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = dry_run() if args.dry_run else run_authenticated()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
