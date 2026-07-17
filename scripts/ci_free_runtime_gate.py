#!/usr/bin/env python3
"""Download and verify official P1 assets inside the free CI runner only."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import urllib.request
from pathlib import Path

from src.player_perception.model_bundle import load_model_bundle


def _download(url: str, destination: Path) -> str:
    digest = hashlib.sha256()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response, destination.open("wb") as handle:
        while block := response.read(1024 * 1024):
            handle.write(block)
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-bundle", type=Path, required=True)
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--config-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--allow-unpinned", action="store_true")
    args = parser.parse_args()
    bundle = load_model_bundle(args.model_bundle)
    report: dict[str, object] = {"schema_version": "1.0", "components": {}}
    temporary_configs = Path(tempfile.mkdtemp(prefix="p1_ci_configs_"))
    try:
        for component in ("detector", "pose"):
            section = bundle[component]
            config_path = temporary_configs / f"{component}.py"
            config_sha = _download(section["config_url"], config_path)
            if config_sha != section["config_sha256"]:
                raise RuntimeError(f"{component} config SHA-256 mismatch: {config_sha}")
            checkpoint_path = args.models_dir / section["checkpoint"]
            checkpoint_sha = _download(section["checkpoint_url"], checkpoint_path)
            expected = section.get("checksum_sha256")
            if expected is None and not args.allow_unpinned:
                raise RuntimeError(f"{component} checkpoint checksum_sha256 is not pinned")
            if expected is not None and checkpoint_sha != expected:
                raise RuntimeError(f"{component} checkpoint SHA-256 mismatch: {checkpoint_sha}")
            report["components"][component] = {
                "config_sha256": config_sha,
                "checkpoint_sha256": checkpoint_sha,
                "checkpoint_pinned": expected is not None,
                "config_url": section["config_url"],
                "checkpoint_url": section["checkpoint_url"],
            }
        report["status"] = (
            "ASSETS_VERIFIED"
            if all(item["checkpoint_pinned"] for item in report["components"].values())
            else "CHECKSUMS_DISCOVERED_NOT_PINNED"
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if report["status"] != "ASSETS_VERIFIED":
            return 2
        return 0
    finally:
        shutil.rmtree(temporary_configs, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
