#!/usr/bin/env python3
"""Export the canonical local Session API V1 OpenAPI candidate."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import argparse
from pathlib import Path


ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "config/platform/session_api_v1.openapi.json"


def canonical_openapi() -> dict:
    from src.platform.api.app import create_app

    return create_app().openapi()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", default=os.getenv("TENNISAI_SOURCE_COMMIT"))
    args = parser.parse_args()
    if not args.source_commit or not re.fullmatch(r"[0-9a-fA-F]{40}", args.source_commit):
        parser.error("--source-commit must be a real 40-character commit SHA")
    ancestor = (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", args.source_commit, "HEAD"], check=False
        ).returncode
        == 0
    )
    if not ancestor:
        parser.error("--source-commit must be an ancestor of HEAD")
    payload = canonical_openapi()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    source_path = ROOT / "config/platform/SESSION_API_SOURCE.json"
    previous_source = {}
    if source_path.exists():
        previous_source = json.loads(source_path.read_text(encoding="utf-8"))
    source = {
        "api_version": "v1",
        "api_style": "LAYERED_FASTAPI_COMPATIBLE_WITH_EXISTING_EXPRESS_MENTAL_MODEL",
        "source_commit": args.source_commit.lower(),
        "source_commit_is_ancestor_of_head": ancestor,
        "generated_at": "2026-07-22T00:00:00Z",
        "sha256": digest,
        "endpoints": sorted(payload.get("paths", {})),
        "operation_ids": sorted(
            operation.get("operationId")
            for path_item in payload.get("paths", {}).values()
            for method, operation in path_item.items()
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        ),
        "schemas": sorted(payload.get("components", {}).get("schemas", {})),
        "gate": previous_source.get(
            "gate", "SESSION_PLATFORM_API_V1_CONTRACT_PENDING_RELEASE_AUDIT"
        ),
    }
    source_path.write_text(
        json.dumps(source, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"path": str(OUTPUT.relative_to(ROOT)), "sha256": digest, "gate": source["gate"]},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
