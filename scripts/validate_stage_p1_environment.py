"""Validate the portable P1 environment without requiring GPU or models."""

from __future__ import annotations

import importlib


def main() -> int:
    importlib.import_module("src.player_perception.cli")
    importlib.import_module("src.player_perception.backends.mock_backend")
    print("P1 environment contract OK: CPU imports only; no model downloads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
