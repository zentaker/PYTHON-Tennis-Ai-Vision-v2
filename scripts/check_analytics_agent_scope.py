#!/usr/bin/env python3
"""Reject changes outside the Analytics agent's exclusive allowlist."""

from __future__ import annotations

import subprocess
from pathlib import Path

BASE_SHA = "e81949bc01cbd2adfca12bd5b3a6a28c3e792fea"
EXPECTED_ROOT = Path("/Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2-analytics")
ORIGINAL_ROOT = Path("/Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2")
EXPECTED_BRANCH = "agent/analytics-stroke-speed-foundation"
PREFIXES = (
    "src/analytics/",
    "docs/analytics/",
    "config/analytics/",
    "tests/fixtures/analytics/",
)
EXACT = {
    "scripts/check_analytics_agent_scope.py",
    ".github/workflows/a1-analytics-foundation-gate.yml",
}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def allowed(path: str) -> bool:
    return (
        path.startswith(PREFIXES)
        or path.startswith("tests/test_analytics_") and path.endswith(".py")
        or path.startswith("docs/agent/tracks/A1_")
        and (path.endswith(".md") or path.endswith(".json"))
        or path in EXACT
    )


def changed_files() -> list[str]:
    paths = set(git("diff", "--name-only", f"{BASE_SHA}...HEAD").splitlines())
    paths.update(git("diff", "--name-only").splitlines())
    paths.update(git("diff", "--cached", "--name-only").splitlines())
    paths.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    return sorted(path for path in paths if path)


def main() -> int:
    root = Path(git("rev-parse", "--show-toplevel")).resolve()
    branch = git("branch", "--show-current")
    head = git("rev-parse", "HEAD")
    changed = changed_files()
    permitted = [path for path in changed if allowed(path)]
    forbidden = [path for path in changed if not allowed(path)]
    root_ok = root == EXPECTED_ROOT and root != ORIGINAL_ROOT
    status = (
        "SAFE_FOR_PARALLEL_WORK"
        if root_ok and branch == EXPECTED_BRANCH and not forbidden
        else "UNSAFE_ANALYTICS_SCOPE"
    )
    print(f"repository root: {root}")
    print(f"worktree root: {root}")
    print(f"branch: {branch}")
    print(f"base SHA: {BASE_SHA}")
    print(f"HEAD: {head}")
    print(f"changed files: {changed}")
    print(f"allowed files: {permitted}")
    print(f"forbidden files: {forbidden}")
    print(f"status: {status}")
    return 0 if status == "SAFE_FOR_PARALLEL_WORK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
