from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_SHA = "bc73f738f5846748250016f1e494f1804bd65274"
SESSION_SHA = "1747670500014598e6d18f5130e8c7f341323f4fe15f96559d9c5da0550f346b"
ANALYSIS_SHA = "329ad9092a1dbf115fe1722f06ea7141b787e454c96f43ec05e7149051087647"

REQUIRED = {
    "path_security": (
        "test_rejects_symlink_to_file_inside_workspace",
        "test_rejects_symlink_to_file_outside_workspace",
        "test_rejects_symlinked_parent_directory",
        "test_rejects_hardlink",
        "test_rejects_duplicate_artifact_descriptor",
        "test_rejects_duplicate_publication_key",
        "test_rejects_single_artifact_size_limit",
        "test_rejects_aggregate_artifact_size_limit",
    ),
    "lease_loss": (
        "test_lease_loss_before_publication_fails_closed",
        "test_real_lease_loss_after_first_publication_compensates_attempt",
        "test_cancel_and_lease_loss_race_never_publishes_stale_result",
    ),
    "shutdown": (
        "test_shutdown_during_processor_stops_without_finalization",
        "test_shutdown_after_publication_before_finalization_compensates",
    ),
    "stale_attempt": ("test_postgres_minio_stale_attempt_cleanup_is_automatic",),
    "workspace_boundary": (
        "test_rejects_replaced_workspace_symlink",
        "test_rejects_symlinked_worker_root",
        "test_rejects_symlinked_run_directory",
        "test_workspace_inode_replacement_fails_closed",
        "test_cleanup_never_follows_replaced_workspace",
    ),
    "bounded_read": ("test_oversized_artifact_rejected_before_unbounded_read",),
    "publication_failure": ("test_partial_upload_is_compensated_without_touching_other_attempt",),
}


def collect_cases(path: Path) -> dict[str, str]:
    root = ET.parse(path).getroot()
    cases: dict[str, str] = {}
    for case in root.findall(".//testcase"):
        name = case.attrib.get("name", "")
        status = "passed"
        if case.find("failure") is not None:
            status = "failed"
        elif case.find("error") is not None:
            status = "errored"
        elif case.find("skipped") is not None:
            status = "skipped"
        cases[name] = status
    return cases


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--workflow-run", required=True)
    parser.add_argument("--unit", type=Path, required=True)
    parser.add_argument("--integration", type=Path, required=True)
    parser.add_argument("--postgres", type=Path, required=True)
    parser.add_argument("--session-openapi", type=Path, required=True)
    parser.add_argument("--analysis-openapi", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.base_sha != BASE_SHA or not re.fullmatch(r"[0-9a-f]{40}", args.head_sha):
        raise SystemExit("invalid base/head SHA")
    if sha256(args.session_openapi) != SESSION_SHA or sha256(args.analysis_openapi) != ANALYSIS_SHA:
        raise SystemExit("frozen OpenAPI hash mismatch")
    cases = {**collect_cases(args.unit), **collect_cases(args.integration), **collect_cases(args.postgres)}
    integration_cases = collect_cases(args.integration)
    postgres_cases = collect_cases(args.postgres)
    if any(status != "passed" for status in {**integration_cases, **postgres_cases}.values()):
        raise SystemExit("integration evidence contains failed, errored, or skipped tests")
    support: dict[str, dict] = {}
    missing: list[str] = []
    for claim, names in REQUIRED.items():
        statuses = [cases.get(name) for name in names]
        if any(status != "passed" for status in statuses):
            missing.extend(name for name, status in zip(names, statuses) if status != "passed")
        support[claim] = {"passed": all(status == "passed" for status in statuses), "tests": list(names)}
    if missing:
        raise SystemExit("required evidence tests missing or not passed: " + ", ".join(missing))
    unit_count = len(collect_cases(args.unit))
    integration_count = len(collect_cases(args.integration))
    evidence = {
        "base_sha": args.base_sha,
        "head_sha": args.head_sha,
        "branch": os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME", "unknown"),
        "workflow_run": args.workflow_run,
        "session_api_sha256": SESSION_SHA,
        "analysis_job_api_sha256": ANALYSIS_SHA,
        "processor_mode": "contract-fixture",
        "fixture_explicitly_enabled": True,
        "fixture_disabled_by_default": True,
        "unit_test_count": unit_count,
        "postgresql_concurrency_test_count": len(postgres_cases),
        "compose_scenario_count": integration_count,
        "supporting_tests": support,
        "videos": 0,
        "secrets": 0,
        "inference": 0,
        "gpu_calls": 0,
        "cloud_calls": 0,
        "spend": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
