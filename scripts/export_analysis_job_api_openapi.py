#!/usr/bin/env python3
"""Export the additive Stage 2B analysis-job OpenAPI snapshot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "config/platform/analysis_job_api_v1.openapi.json"


def main() -> int:
    from src.platform.api.analysis_app import create_analysis_app

    payload = create_analysis_app().openapi()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    OUTPUT.write_text(rendered, encoding="utf-8")
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    print(json.dumps({"path": str(OUTPUT.relative_to(ROOT)), "sha256": digest}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
