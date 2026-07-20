#!/usr/bin/env python3
"""Build the small non-decodable packaging fixture twice for CI evidence."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from src.product.analysis_bundle.builder import build_bundle

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/product/analysis_bundle_v1"
OUT = ROOT / ".artifacts/stage0b-analysis-bundle-fixture"


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    descriptor = ROOT / "tests/fixtures/product/analysis_bundle_v1/bundle-inputs.json"
    with tempfile.TemporaryDirectory(prefix="stage0b-source-") as temp:
        source = Path(temp) / "fixture.mp4"
        source.write_bytes(b"non-decodable packaging fixture; not a real video")
        first = Path(temp) / "first"
        second = Path(temp) / "second"
        result_a = build_bundle(
            source, descriptor, "fixture-session-001", "FAST", "hard", first, "2026-07-20T00:00:00Z"
        )
        result_b = build_bundle(
            source,
            descriptor,
            "fixture-session-001",
            "FAST",
            "hard",
            second,
            "2026-07-20T00:00:00Z",
        )
        if result_a["fingerprint"] != result_b["fingerprint"]:
            raise SystemExit("non-deterministic fixture fingerprint")
        shutil.copytree(first, OUT / "bundle")
        for name in ("manifest.json", "session.json", "rallies.json"):
            shutil.copy2(first / name, OUT / name)
        (OUT / "build-report.json").write_text(
            json.dumps(
                {
                    "first": result_a,
                    "second": result_b,
                    "fingerprints_identical": True,
                    "source_fixture": "non-decodable packaging fixture",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        (OUT / "validation-report.json").write_text(
            json.dumps(
                {
                    "session_id": result_a["session_id"],
                    "fingerprint": result_a["fingerprint"],
                    "files_verified": result_a["files_verified"],
                    "source_verification": "not requested; source is temporary",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
