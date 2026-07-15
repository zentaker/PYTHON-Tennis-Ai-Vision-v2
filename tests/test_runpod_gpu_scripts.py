from __future__ import annotations

import stat
import subprocess
from pathlib import Path


GPU_SCRIPTS = [
    Path("scripts/gpu/runpod_bootstrap.sh"),
    Path("scripts/gpu/verify_runpod_environment.sh"),
    Path("scripts/gpu/run_stage2_a2_remote.sh"),
    Path("scripts/gpu/download_stage2_results.sh"),
]


def test_gpu_scripts_are_executable_and_valid_bash() -> None:
    for script in GPU_SCRIPTS:
        assert script.stat().st_mode & stat.S_IXUSR
        subprocess.run(["bash", "-n", str(script)], check=True)


def test_bootstrap_is_frozen_and_never_starts_inference() -> None:
    source = GPU_SCRIPTS[0].read_text(encoding="utf-8")

    assert "uv sync --frozen" in source
    assert "LOCK_BEFORE" in source and "LOCK_AFTER" in source
    assert "--require-runtime" in source
    assert "src.tracker.wasb_runner" not in source


def test_remote_runner_pins_commit_and_only_runs_stage_2() -> None:
    source = GPU_SCRIPTS[2].read_text(encoding="utf-8")

    assert "git fetch origin --prune" in source
    assert 'git -C "$LOCAL_REPO_DIR" show' in source
    assert 'git checkout --detach "$RESOLVED_SHA"' in source
    assert "git clean" not in source
    assert "python -m src.tracker.wasb_runner" in source
    assert "csv_frames_verified=527" in source
    assert "overlay_frames_verified=527" in source
    assert "git_commit" in source
    assert "src.tracker.trajectory_smoothing" not in source


def test_downloader_backs_up_before_installing_checksum_verified_files() -> None:
    source = GPU_SCRIPTS[3].read_text(encoding="utf-8")

    assert "remote_sha=" in source
    assert "local_sha=" in source
    assert 'mv "$local_path" "$backup_path"' in source
    assert 'mv "$temp_path" "$local_path"' in source
    assert "wasb_detections.csv" in source
    assert "wasb_detections_overlay.mp4" in source
    assert "inference_report.json" in source


def test_example_config_contains_placeholders_and_no_private_material() -> None:
    config = Path("config/runpod/stage2_a2.env.example").read_text(encoding="utf-8")

    assert 'RUNPOD_HOST="HOST_PUBLICO_DEL_POD"' in config
    assert "RUNPOD_COMMIT_SHA" in config
    assert "BEGIN OPENSSH PRIVATE KEY" not in config
    assert "github_pat_" not in config
