#!/usr/bin/env python3
"""Audit P1 runtime wiring locally without GPU or model inference."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.player_perception.backends.openmmlab_backend import OpenMMLabBackend  # noqa: E402
from src.player_perception.model_bundle import load_model_bundle  # noqa: E402
from scripts.validate_stage_p1_outputs import validate  # noqa: E402
from src.project.clip_manifest import ClipManifest  # noqa: E402
from src.video.canonical_frames import iter_canonical_frames  # noqa: E402


CLIP = ROOT / "data/clips/nivel_a2_01"
FRAMES = [139, 140, 200, 201, 287, 288, 351, 352, 434, 435]


def audit() -> dict[str, object]:
    checks: dict[str, bool] = {}
    manifest_path = ROOT / "config/player_perception/p1_openmmlab.json"
    load_model_bundle(manifest_path)
    checks["model_manifest"] = True
    checks["canonical_decoder_import"] = callable(iter_canonical_frames)
    backend = OpenMMLabBackend(model_bundle=manifest_path, validate_only=True)
    checks["openmmlab_validate_only"] = not backend.initialized
    source = CLIP / "source.mp4"
    clip_manifest = ClipManifest.read(CLIP / "clip_manifest.json")
    checks["video_present"] = source.is_file()
    checks["smoke_script"] = (ROOT / "scripts/run_stage_p1_smoke.sh").is_file()
    checks["output_validator"] = (ROOT / "scripts/validate_stage_p1_outputs.py").is_file()
    checks["container_contract"] = all(
        (ROOT / "containers/player-perception" / name).is_file()
        for name in (
            "Dockerfile",
            "requirements-runtime.txt",
            "requirements-openmmlab.txt",
            "constraints.txt",
            "COMPATIBILITY.md",
        )
    )
    checks["backend_process_implemented"] = "NotImplemented" not in (
        ROOT / "src/player_perception/backends/openmmlab_backend.py"
    ).read_text(encoding="utf-8")
    source_text = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "src/player_perception").rglob("*.py")
    )
    checks["no_semantic_constraints_input"] = "semantic_constraints" not in source_text
    if source.is_file():
        decoded_ids = []
        for frame in iter_canonical_frames(source, clip_manifest):
            if frame.frame_id in FRAMES:
                decoded_ids.append(frame.frame_id)
        checks["real_video_decoding"] = decoded_ids == FRAMES
    else:
        checks["real_video_decoding"] = False
    with tempfile.TemporaryDirectory(prefix="p1_runtime_audit_") as directory:
        output_dir = Path(directory) / "outputs"
        command = [
            sys.executable,
            "-m",
            "src.player_perception.cli",
            "--clip-id",
            "nivel_a2_01",
            "--backend",
            "mock",
            "--device",
            "cpu",
            "--video",
            str(source),
            "--manifest",
            str(CLIP / "clip_manifest.json"),
            "--homography",
            str(CLIP / "homography.json"),
            "--events",
            str(ROOT / "outputs/nivel_a2_01/stage_4/events.json"),
            "--trajectory",
            str(ROOT / "outputs/nivel_a2_01/stage_3/smoothed_trajectory.csv"),
            "--output-dir",
            str(output_dir),
            "--frames",
            ",".join(map(str, FRAMES)),
        ]
        subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
        validate(output_dir, FRAMES)
        checks["mock_real_frame_e2e"] = True
    checks["all_static_and_local_checks"] = all(checks.values())
    status = (
        "READY_FOR_GPU_PROVIDER_SMOKE"
        if checks["all_static_and_local_checks"]
        else "RUNTIME_INCOMPLETE"
    )
    return {
        "schema_version": "1.0",
        "status": status,
        "checks": checks,
        "not_executed": [
            "OpenMMLab model inference",
            "CUDA/PyTorch GPU execution",
            "Docker build or run",
            "cloud provider setup",
            "full 527-frame job",
            "Stage 5B/5C/6",
        ],
        "next_action": "ChatGPT debe auditar P1_RUNTIME_READINESS y después evaluar proveedores actuales contra GPU_PROVIDER_ACCEPTANCE_GATE.",
    }


def main() -> int:
    report = audit()
    destination = ROOT / "docs/agent/P1_RUNTIME_READINESS.json"
    destination.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "READY_FOR_GPU_PROVIDER_SMOKE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
