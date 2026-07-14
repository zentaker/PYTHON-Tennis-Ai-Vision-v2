"""Lightweight smoke test for the auxiliary Replit environment.

This archived auxiliary-environment check intentionally avoids OpenCV, WASB,
videos, checkpoints, and heavy tracker dependencies.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


LIGHTWEIGHT_MODULES = (
    "src.events.event_schema",
    "src.events.event_loader",
)


def import_required(module_name: str) -> None:
    importlib.import_module(module_name)
    print(f"OK import {module_name}")


def main() -> int:
    for module_name in LIGHTWEIGHT_MODULES:
        import_required(module_name)

    print("OK Replit smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
