#!/usr/bin/env python3
"""Validate the reproducible, additive Stage 2B analysis-job contract."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
SNAPSHOT = ROOT / "config/platform/analysis_job_api_v1.openapi.json"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN = re.compile(r"(?i)(password|secret|credential|access[_-]?key|authorization:|x-amz-signature)")


def _canonical() -> dict:
    from src.platform.api.analysis_app import create_analysis_app

    return create_analysis_app().openapi()


def main() -> int:
    if not SNAPSHOT.exists():
        raise SystemExit(f"missing snapshot: {SNAPSHOT}")
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    actual = _canonical()
    expected_bytes = json.dumps(expected, indent=2, sort_keys=True).encode() + b"\n"
    actual_bytes = json.dumps(actual, indent=2, sort_keys=True).encode() + b"\n"
    if expected_bytes != actual_bytes:
        raise SystemExit("analysis OpenAPI snapshot is not reproducible")
    operations = []
    for path, item in actual.get("paths", {}).items():
        if not path.startswith("/api/v1/"):
            raise SystemExit(f"endpoint outside /api/v1: {path}")
        for method, operation in item.items():
            if method.lower() in {"get", "post", "put", "patch", "delete"}:
                operations.append((path, method.upper(), operation.get("operationId", "")))
    ids = [operation[2] for operation in operations]
    if not ids or len(ids) != len(set(ids)) or any(not value for value in ids):
        raise SystemExit("operation IDs must be present and unique")
    expected_paths = {
        "/api/v1/analysis-runs",
        "/api/v1/analysis-runs/{run_id}",
        "/api/v1/analysis-runs/{run_id}/cancel",
        "/api/v1/sessions/{session_id}/analysis-runs",
    }
    if set(path for path, _, _ in operations) != expected_paths:
        raise SystemExit("analysis endpoint set changed unexpectedly")
    text = SNAPSHOT.read_text(encoding="utf-8")
    if FORBIDDEN.search(text) or "http://" in text or "https://" in text:
        raise SystemExit("secrets or external URLs found in analysis OpenAPI")
    digest = hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest()
    if not SHA_RE.fullmatch(digest):
        raise SystemExit("invalid snapshot digest")
    print(json.dumps({"operations": operations, "sha256": digest}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
