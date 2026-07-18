#!/usr/bin/env python3
"""Prepare a local-only Modal cleanup audit; never calls Modal by default."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def audit(root: Path) -> dict[str, object]:
    output_dir = root / "outputs/nivel_a2_01/stage_p1_modal_smoke"
    package = root / ".modal_smoke/nivel_a2_01/inputs/p1_smoke_manifest.json"
    return {
        "status": "CHECKLIST_READY",
        "remote_commands_not_executed": True,
        "remote_checks": [
            "modal app list",
            "modal app stop APP_ID (only when an App remains)",
            "modal container list",
        ],
        "local_outputs_downloaded": output_dir.is_dir() and any(output_dir.iterdir()),
        "local_assets_persisted": package.is_file(),
        "persistent_volume_names": ["tennisai-p1-assets", "tennisai-p1-results"],
        "volume_cleanup_command": "modal volume delete VOLUME_NAME",
        "warning": "Do not delete either Volume until outputs and reports are backed up.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(audit(args.root.resolve()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
