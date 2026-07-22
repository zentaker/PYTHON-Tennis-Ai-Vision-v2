#!/usr/bin/env python3
"""Export the canonical local Session API V1 OpenAPI candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "config/platform/session_api_v1.openapi.json"


def canonical_openapi() -> dict:
    from src.platform.api.app import create_app

    return create_app().openapi()


def main() -> int:
    payload = canonical_openapi()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    source = {
        "api_version": "v1",
        "api_style": "LAYERED_FASTAPI_COMPATIBLE_WITH_EXISTING_EXPRESS_MENTAL_MODEL",
        "core_commit": "generated-at-build-time",
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
        "gate": "SESSION_PLATFORM_API_V1_CONTRACT_CANDIDATE",
    }
    (ROOT / "config/platform/SESSION_API_SOURCE.json").write_text(
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
