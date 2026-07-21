#!/usr/bin/env python3
"""Build a deterministic synthetic Stage 1A bundle for CI evidence."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from src.product.single_rally.importer import import_single_rally
from src.product.single_rally.validation import validate_single_rally_bundle

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/product/single_rally_v1"
OUT = ROOT / ".artifacts/stage1a-single-rally-import"


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="stage1a-source-") as temp_name:
        temp = Path(temp_name)
        source = temp / "synthetic_rally.mp4"
        source.write_bytes(b"synthetic_contract_fixture; not a real video")
        descriptor = temp / "single-rally-inputs.json"
        payload = json.loads((FIXTURE / "single-rally-inputs.json").read_text())
        for key, value in payload["files"].items():
            payload["files"][key] = str((FIXTURE / value).resolve())
        descriptor.write_text(json.dumps(payload, indent=2) + "\n")
        first = temp / "first"
        second = temp / "second"
        result_a = import_single_rally(
            source,
            descriptor,
            "fixture-session-001",
            "rally-001",
            "STANDARD",
            "hard",
            first,
            "2026-07-20T00:00:00Z",
        )
        result_b = import_single_rally(
            source,
            descriptor,
            "fixture-session-001",
            "rally-001",
            "STANDARD",
            "hard",
            second,
            "2026-07-20T00:00:00Z",
        )
        if result_a["fingerprint"] != result_b["fingerprint"]:
            raise SystemExit("non-deterministic Stage 1A fixture")
        validate_single_rally_bundle(first)
        shutil.copytree(first, OUT / "bundle")
        for name in (
            "manifest.json",
            "session.json",
            "rallies.json",
            "events.jsonl",
            "ball_track.jsonl",
            "court_map.json",
            "metrics.json",
        ):
            shutil.copy2(first / name, OUT / name)
        manifest = json.loads((first / "manifest.json").read_text())
        (OUT / "import-report.json").write_text(
            json.dumps(
                {
                    **result_a,
                    "fixture": "synthetic_contract_fixture",
                    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    "fingerprints_identical": True,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        (OUT / "validation-report.json").write_text(
            json.dumps(
                {
                    "fingerprint": result_a["fingerprint"],
                    "files_verified": result_a["files_verified"],
                    "rally_id": result_a["rally_id"],
                    "source_sha256": manifest["source_video"]["sha256"],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
