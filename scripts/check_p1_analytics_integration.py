#!/usr/bin/env python3
"""Fail closed when the P1/Analytics integration history or scope drifts."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

EXPECTED_ROOT = Path("/Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2-integration")
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / "config/integration/p1_analytics_integration.json"
ALLOWED_FILES = {
    ".github/workflows/p1-analytics-integration-gate.yml",
    "config/integration/p1_analytics_integration.json",
    "docs/agent/tracks/INTEGRATION_P1_ANALYTICS.md",
    "docs/integration/P1_ANALYTICS_INTEGRATION_MANIFEST.md",
    "docs/integration/P1_ANALYTICS_INTEGRATION_REPORT.md",
    "scripts/check_p1_analytics_integration.py",
    "tests/test_p1_analytics_integration.py",
}


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=REPOSITORY_ROOT, text=True, stderr=subprocess.STDOUT
    ).strip()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text())
    root = Path(git("rev-parse", "--show-toplevel")).resolve()
    branch = git("branch", "--show-current") or os.environ.get("GITHUB_REF_NAME", "")
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    require(root == EXPECTED_ROOT or in_actions, f"unexpected root: {root}")
    require(branch == manifest["integration_branch"], f"unexpected branch: {branch}")

    p1 = manifest["p1_source_sha"]
    analytics = manifest["analytics_source_sha"]
    common_base = manifest["common_base_sha"]
    merge_sha = manifest["merge_sha"]
    for source in (p1, analytics):
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", source, "HEAD"],
            cwd=root,
            check=True,
        )
    require(git("cat-file", "-t", merge_sha) == "commit", "merge SHA is not a commit")
    parents = git("show", "-s", "--format=%P", merge_sha).split()
    require(parents == [p1, analytics], f"unexpected merge parents: {parents}")
    require(git("merge-base", p1, analytics) == common_base, "common base mismatch")

    changed = [line for line in git("diff", "--name-only", f"{merge_sha}..HEAD").splitlines() if line]
    forbidden = sorted(set(changed) - ALLOWED_FILES)
    require(not forbidden, f"forbidden post-merge changes: {forbidden}")

    for relative in (
        "src/player_perception",
        "src/analytics",
        "config/providers/lightning_p1_smoke.json",
        "config/analytics/stroke_analytics.schema.json",
    ):
        require((root / relative).exists(), f"required integration input missing: {relative}")

    lightning = json.loads((root / "config/providers/lightning_p1_smoke.json").read_text())
    modal = json.loads((root / "config/providers/modal_p1_smoke.json").read_text())
    require(modal["provider_status"] == "REJECTED_PAYMENT_METHOD_POLICY", "Modal not rejected")
    require(modal["remote_execution_authorized"] is False, "Modal remote execution enabled")
    require(lightning["account_status"] == "NOT_CREATED", "Lightning account state changed")
    require(lightning["remote_execution_authorized"] is False, "Lightning remote execution enabled")

    print(f"branch: {branch}")
    print(f"root: {root}")
    print(f"common base: {common_base}")
    print(f"P1 source: {p1}")
    print(f"Analytics source: {analytics}")
    print(f"merge SHA: {merge_sha}")
    print(f"merge parents: {' '.join(parents)}")
    print(f"post-merge changed files: {changed}")
    print(f"forbidden post-merge changes: {forbidden}")
    print("status: SAFE_P1_ANALYTICS_INTEGRATION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
