from __future__ import annotations

import os
import shutil
from pathlib import Path
from uuid import UUID


def attempt_workspace(root: str | Path, run_id: UUID, attempt: int) -> Path:
    if attempt < 1:
        raise ValueError("attempt must be positive")
    path = Path(root).expanduser().resolve() / str(run_id) / str(attempt)
    path.mkdir(parents=True, exist_ok=False)
    return path


def cleanup_workspace(root: str | Path, workspace: Path) -> None:
    """Remove exactly one attempt below the configured worker root."""

    root_path = Path(root).expanduser().resolve()
    target = workspace.resolve()
    if target == root_path or root_path not in target.parents:
        raise ValueError("workspace is outside worker root")
    shutil.rmtree(target)
    # Remove empty run directory, but never the configured root or siblings.
    run_dir = target.parent
    try:
        run_dir.rmdir()
    except OSError:
        pass


def ensure_worker_root(root: str | Path) -> Path:
    path = Path(root).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    if not os.access(path, os.W_OK):
        raise OSError("worker root is not writable")
    return path
