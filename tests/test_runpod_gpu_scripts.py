from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import tarfile
from pathlib import Path


GPU_SCRIPTS = [
    Path("scripts/gpu/runpod_bootstrap.sh"),
    Path("scripts/gpu/verify_runpod_environment.sh"),
    Path("scripts/gpu/run_stage2_a2_remote.sh"),
    Path("scripts/gpu/download_stage2_results.sh"),
    Path("scripts/gpu/runpod_ssh.sh"),
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
    assert "frame_timestamps.json" in source
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
    assert "download_with_runpodctl" in source
    assert "download_with_scp" in source


def _fake_ssh(tmp_path: Path) -> tuple[Path, Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    ssh = fake_bin / "ssh"
    ssh.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@"\n', encoding="utf-8")
    ssh.chmod(0o700)
    key = tmp_path / "id_test"
    key.touch(mode=0o600)
    return fake_bin, key


def test_ssh_helper_builds_proxy_without_port(tmp_path: Path) -> None:
    fake_bin, key = _fake_ssh(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "RUNPOD_ENV_FILE": str(tmp_path / "missing.env"),
        "RUNPOD_SSH_MODE": "proxy",
        "RUNPOD_SSH_TARGET": "temporary-user@ssh.runpod.io",
        "RUNPOD_SSH_KEY": str(key),
    }

    result = subprocess.run(
        ["bash", "scripts/gpu/runpod_ssh.sh", "hostname"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    arguments = result.stdout.splitlines()
    assert "temporary-user@ssh.runpod.io" in arguments
    assert "hostname" in arguments
    assert "-p" not in arguments


def test_ssh_helper_accepts_private_config_alias(tmp_path: Path) -> None:
    fake_bin, key = _fake_ssh(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "RUNPOD_ENV_FILE": str(tmp_path / "missing.env"),
        "RUNPOD_SSH_MODE": "proxy",
        "RUNPOD_SSH_TARGET": "tennis-runpod-a2",
        "RUNPOD_SSH_KEY": str(key),
    }

    result = subprocess.run(
        ["bash", "scripts/gpu/runpod_ssh.sh", "hostname"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert "tennis-runpod-a2" in result.stdout.splitlines()


def test_ssh_helper_builds_exposed_tcp_with_port(tmp_path: Path) -> None:
    fake_bin, key = _fake_ssh(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "RUNPOD_ENV_FILE": str(tmp_path / "missing.env"),
        "RUNPOD_SSH_MODE": "exposed_tcp",
        "RUNPOD_HOST": "gpu.example.test",
        "RUNPOD_SSH_USER": "root",
        "RUNPOD_SSH_PORT": "23456",
        "RUNPOD_SSH_KEY": str(key),
    }

    result = subprocess.run(
        ["bash", "scripts/gpu/runpod_ssh.sh", "hostname"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    arguments = result.stdout.splitlines()
    assert "root@gpu.example.test" in arguments
    assert arguments[arguments.index("-p") + 1] == "23456"


def test_ssh_helper_rejects_incomplete_proxy_configuration(tmp_path: Path) -> None:
    _fake_bin, key = _fake_ssh(tmp_path)
    env = {
        **os.environ,
        "RUNPOD_ENV_FILE": str(tmp_path / "missing.env"),
        "RUNPOD_SSH_MODE": "proxy",
        "RUNPOD_SSH_KEY": str(key),
    }

    result = subprocess.run(
        ["bash", "scripts/gpu/runpod_ssh.sh", "hostname"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 2
    assert "RUNPOD_SSH_TARGET" in result.stderr


def test_proxy_downloader_uses_runpodctl_and_never_scp(tmp_path: Path) -> None:
    local_repo = tmp_path / "repo"
    (local_repo / ".git").mkdir(parents=True)
    payload = tmp_path / "payload"
    files = {
        "data/clips/nivel_a2_01/wasb_detections.csv": "frame_id\n0\n",
        "outputs/nivel_a2_01/stage_2/wasb_detections_overlay.mp4": "overlay",
        "outputs/nivel_a2_01/stage_2/inference_report.json": "{}\n",
        "outputs/nivel_a2_01/stage_2/logs/stage2.log": "log\n",
    }
    for relative_path, contents in files.items():
        path = payload / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
    bundle = tmp_path / "stage2_a2_results_deadbeef0000.tar.gz"
    with tarfile.open(bundle, "w:gz") as archive:
        for relative_path in files:
            archive.add(payload / relative_path, arcname=relative_path)
    expected_sha = hashlib.sha256(bundle.read_bytes()).hexdigest()

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    runpodctl = fake_bin / "runpodctl"
    runpodctl.write_text(
        '#!/usr/bin/env bash\ncp "$FAKE_BUNDLE" .\n',
        encoding="utf-8",
    )
    runpodctl.chmod(0o700)
    scp_marker = tmp_path / "scp_was_called"
    scp = fake_bin / "scp"
    scp.write_text(
        f'#!/usr/bin/env bash\ntouch "{scp_marker}"\nexit 99\n',
        encoding="utf-8",
    )
    scp.chmod(0o700)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "RUNPOD_ENV_FILE": str(tmp_path / "missing.env"),
        "RUNPOD_SSH_MODE": "proxy",
        "RUNPOD_TRANSFER_MODE": "runpodctl",
        "RUNPOD_TRANSFER_CODE": "temporary-code",
        "RUNPOD_BUNDLE_SHA256": expected_sha,
        "FAKE_BUNDLE": str(bundle),
    }

    subprocess.run(
        ["bash", "scripts/gpu/download_stage2_results.sh", str(local_repo)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert not scp_marker.exists()
    for relative_path in files:
        assert (local_repo / relative_path).is_file()


def test_example_config_contains_placeholders_and_no_private_material() -> None:
    config = Path("config/runpod/stage2_a2.env.example").read_text(encoding="utf-8")

    assert 'RUNPOD_SSH_MODE="proxy"' in config
    assert 'RUNPOD_TRANSFER_MODE="runpodctl"' in config
    assert 'RUNPOD_SSH_TARGET="USUARIO_TEMPORAL@ssh.runpod.io"' in config
    assert 'RUNPOD_HOST="HOST_PUBLICO_DEL_POD"' in config
    assert "RUNPOD_COMMIT_SHA" in config
    assert "BEGIN OPENSSH PRIVATE KEY" not in config
    assert "github_pat_" not in config
