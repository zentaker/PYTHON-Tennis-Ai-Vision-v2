"""Lightweight smoke test for the auxiliary Replit environment.

This script intentionally avoids OpenCV, WASB, videos, checkpoints, and heavy
tracker dependencies. It only verifies imports that should be safe in a minimal
code/docs/test workspace.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


LIGHTWEIGHT_MODULES = (
    "src",
    "src.court.coordinates",
    "src.tracker.trajectory_io",
)

EVENT_LOADER_CANDIDATES = (
    "src.events.event_loader",
    "src.event_loader",
    "event_loader",
)


def import_required(module_name: str) -> None:
    importlib.import_module(module_name)
    print(f"OK import {module_name}")


def import_event_loader() -> str:
    errors: list[str] = []

    for module_name in EVENT_LOADER_CANDIDATES:
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            errors.append(f"{module_name}: {exc}")
            continue

        print(f"OK import {module_name}")
        return module_name

    print("FAIL event_loader import")
    for error in errors:
        print(f"  {error}")
    raise SystemExit(1)


def main() -> int:
    for module_name in LIGHTWEIGHT_MODULES:
        import_required(module_name)

    import_event_loader()

    print("OK Replit smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
