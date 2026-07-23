#!/usr/bin/env python3
"""Audit saved Stage 2B runtime evidence without accepting placeholders."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SECRET = re.compile(r"(?i)(password|secret|credential|access[_-]?key|token=|x-amz-signature)")


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("artifacts/analysis-job-runtime.json")
    if not path.exists():
        raise SystemExit(f"runtime evidence missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("videos_processed", 0) != 0 or payload.get("gpu_calls", 0) != 0:
        raise SystemExit("runtime audit must contain zero video/GPU work")
    if SECRET.search(path.read_text(encoding="utf-8")):
        raise SystemExit("runtime evidence contains a secret-like value")
    required = {"state_machine", "idempotency", "lease_recovery", "artifact_validation"}
    missing = required.difference(payload.get("observations", {}))
    if missing:
        raise SystemExit(f"runtime evidence missing observations: {sorted(missing)}")
    print(json.dumps({"status": "observed", "observations": payload["observations"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
