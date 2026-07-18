#!/usr/bin/env python3
"""Explicit model fetcher; never imported or invoked by the runtime."""

from __future__ import annotations

import argparse
import shutil
import tempfile
import urllib.request
from pathlib import Path

from src.player_perception.model_bundle import load_model_bundle, resolve_model_path, sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch one manifest model after explicit approval")
    parser.add_argument("--model-bundle", type=Path, required=True)
    parser.add_argument("--component", choices=["detector", "pose"], required=True)
    parser.add_argument(
        "--source-url", help="Optional override; defaults to manifest checkpoint_url"
    )
    parser.add_argument("--models-dir", type=Path, default=Path("/models"))
    args = parser.parse_args()
    bundle = load_model_bundle(args.model_bundle)
    section = bundle[args.component]
    checksum = section.get("checksum_sha256")
    if not checksum:
        raise SystemExit(
            f"{args.component}.checksum_sha256 is null; record the verified SHA-256 before fetching"
        )
    destination = resolve_model_path(args.models_dir, section["checkpoint"])
    source_url = args.source_url or section["checkpoint_url"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and sha256_file(destination) == checksum:
        print(f"already present and verified: {destination}")
        return 0
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with (
            urllib.request.urlopen(source_url, timeout=120) as response,
            temporary.open("wb") as output,
        ):
            shutil.copyfileobj(response, output)
        actual = sha256_file(temporary)
        if actual != checksum:
            raise SystemExit(
                f"SHA-256 mismatch for {args.component}: expected {checksum}, got {actual}"
            )
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"fetched and verified: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
