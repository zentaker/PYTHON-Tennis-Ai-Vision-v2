from __future__ import annotations

import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


def _absolute(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    return candidate if candidate.is_absolute() else Path.cwd() / candidate


def _directory_identity(path: Path, label: str) -> tuple[int, int]:
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise ValueError(f"{label} is unavailable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise ValueError(f"{label} is not a real directory")
    return info.st_dev, info.st_ino


def _assert_no_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode):
            raise ValueError("workspace path contains a symlink")


@dataclass(frozen=True)
class WorkspaceIdentity:
    root: tuple[int, int]
    run: tuple[int, int]
    attempt: tuple[int, int]


def ensure_worker_root(root: str | Path) -> Path:
    """Create and validate a real, non-symlink worker root.

    The path is intentionally never resolved: resolving a processor-controlled
    replacement would redefine the trust boundary.  Existing components are
    inspected with ``lstat`` before the directory is accepted.
    """

    path = _absolute(root)
    path.mkdir(parents=True, exist_ok=True)
    _assert_no_symlink_components(path)
    _directory_identity(path, "worker root")
    if not os.access(path, os.W_OK):
        raise OSError("worker root is not writable")
    return path


def attempt_workspace(root: str | Path, run_id: UUID, attempt: int) -> Path:
    if attempt < 1:
        raise ValueError("attempt must be positive")
    root_path = _absolute(root)
    _assert_no_symlink_components(root_path)
    _directory_identity(root_path, "worker root")
    run_path = root_path / str(run_id)
    if run_path.exists() or run_path.is_symlink():
        _directory_identity(run_path, "run directory")
    else:
        run_path.mkdir()
    attempt_path = run_path / str(attempt)
    if attempt_path.exists() or attempt_path.is_symlink():
        raise FileExistsError("attempt workspace already exists")
    attempt_path.mkdir()
    _directory_identity(attempt_path, "attempt workspace")
    return attempt_path


def capture_workspace_identity(root: str | Path, workspace: Path) -> WorkspaceIdentity:
    root_path = _absolute(root)
    workspace_path = _absolute(workspace)
    if root_path not in workspace_path.parents:
        raise ValueError("workspace is outside worker root")
    run_path = workspace_path.parent
    return WorkspaceIdentity(
        root=_directory_identity(root_path, "worker root"),
        run=_directory_identity(run_path, "run directory"),
        attempt=_directory_identity(workspace_path, "attempt workspace"),
    )


def validate_workspace_identity(
    root: str | Path, workspace: Path, identity: WorkspaceIdentity
) -> None:
    current = capture_workspace_identity(root, workspace)
    if current != identity:
        raise ValueError("workspace identity changed")


def cleanup_workspace(
    root: str | Path, workspace: Path, identity: WorkspaceIdentity | None = None
) -> None:
    """Remove exactly one attempt without following a replaced workspace."""

    root_path = _absolute(root)
    workspace_path = _absolute(workspace)
    if root_path not in workspace_path.parents:
        raise ValueError("workspace is outside worker root")
    if identity is not None:
        validate_workspace_identity(root_path, workspace_path, identity)
    else:
        capture_workspace_identity(root_path, workspace_path)
    shutil.rmtree(workspace_path)
    run_path = workspace_path.parent
    try:
        _directory_identity(run_path, "run directory")
        run_path.rmdir()
    except OSError:
        pass
