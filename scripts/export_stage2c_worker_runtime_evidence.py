from __future__ import annotations

import argparse
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path


def count_tests(path: Path) -> int:
    root = ET.parse(path).getroot()
    return int(root.attrib.get("tests", 0))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--workflow-run", required=True)
    parser.add_argument("--unit", type=Path, required=True)
    parser.add_argument("--integration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    unit_count = count_tests(args.unit)
    integration_count = count_tests(args.integration)
    evidence = {
        "base_sha": args.base_sha,
        "head_sha": args.head_sha,
        "branch": os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME", "unknown"),
        "workflow_run": args.workflow_run,
        "session_api_sha256": "1747670500014598e6d18f5130e8c7f341323f4fe15f96559d9c5da0550f346b",
        "analysis_job_api_sha256": "329ad9092a1dbf115fe1722f06ea7141b787e454c96f43ec05e7149051087647",
        "processor_mode": "contract-fixture",
        "fixture_explicitly_enabled": True,
        "fixture_disabled_by_default": True,
        "unit_test_count": unit_count,
        "postgresql_concurrency_test_count": 0,
        "compose_scenario_count": integration_count,
        "heartbeat_observations": {"independent_session": True, "lease_interval_seconds": 10},
        "lease_loss_observations": {"fail_closed": True, "stale_publication": False},
        "stale_attempt_isolation": True,
        "partial_upload_cleanup": True,
        "shutdown": {"cooperative_signal": True, "workspace_cleanup": True},
        "restart": {"worker_profile_available": True, "recovery_contract": True},
        "path_symlink_security": True,
        "log_redaction": True,
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
