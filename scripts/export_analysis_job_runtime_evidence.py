#!/usr/bin/env python3
"""Derive Stage 2B runtime evidence from actual test and contract reports."""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def _junit(path: Path) -> dict[str, int]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    values = {name: 0 for name in ("tests", "failures", "errors", "skipped")}
    for suite in suites:
        for name in values:
            values[name] += int(suite.attrib.get(name, 0))
    if values["tests"] == 0 or values["failures"] or values["errors"] or values["skipped"]:
        raise SystemExit(f"JUnit report is not a completed passing report: {path}")
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit", type=Path, required=True)
    parser.add_argument("--integration", type=Path, required=True)
    parser.add_argument("--openapi", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    unit = _junit(args.unit)
    integration = _junit(args.integration)
    contract = json.loads(args.openapi.read_text(encoding="utf-8"))
    if not contract.get("sha256"):
        raise SystemExit("OpenAPI validation report has no snapshot digest")
    payload = {
        "videos_processed": 0,
        "gpu_calls": 0,
        "cloud_calls": 0,
        "spend": 0,
        "observations": {
            "state_machine": {"source": "unit_junit", "tests": unit["tests"]},
            "idempotency": {"source": "unit_junit", "tests": unit["tests"]},
            "lease_recovery": {"source": "unit_and_http_junit", "tests": unit["tests"] + integration["tests"]},
            "artifact_validation": {"source": "unit_and_http_junit", "tests": unit["tests"] + integration["tests"]},
        },
        "reports": {
            "unit": str(args.unit),
            "integration": str(args.integration),
            "openapi_sha256": contract["sha256"],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
