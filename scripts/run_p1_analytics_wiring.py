#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analytics.p1_wiring import write_wiring_outputs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p1-results", type=Path, required=True)
    parser.add_argument("--stage4-events", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--p1-source-sha", required=True)
    parser.add_argument("--p1-results-sha256", required=True)
    args = parser.parse_args()
    report = write_wiring_outputs(args.p1_results, args.stage4_events, args.output_dir, p1_source_sha=args.p1_source_sha, p1_results_sha256=args.p1_results_sha256)
    (args.output_dir / "run.log").write_text(json.dumps(report, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "P1_ANALYTICS_FUNCTIONAL_WIRING_PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
