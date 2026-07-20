from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import BundleInputError

PROFILE_PATH = Path(__file__).parents[3] / "config/product/processing_profiles_v1.json"


def resolve_profile(name: str, path: Path = PROFILE_PATH) -> dict[str, Any]:
    profiles = json.loads(path.read_text())["profiles"]
    if name not in profiles:
        raise BundleInputError(f"unknown processing profile: {name}")

    def visit(current: str, stack: tuple[str, ...]) -> dict[str, Any]:
        if current in stack:
            raise BundleInputError(f"profile inheritance cycle: {' -> '.join(stack + (current,))}")
        raw = profiles.get(current)
        if raw is None:
            raise BundleInputError(f"unknown inherited profile: {current}")
        result: dict[str, Any] = {key: value for key, value in raw.items() if key != "extends"}
        parent = raw.get("extends")
        if parent:
            inherited = visit(parent, stack + (current,))
            merged = dict(inherited)
            merged_caps = dict(inherited.get("capabilities", {}))
            merged_caps.update(result.get("capabilities", {}))
            merged["capabilities"] = merged_caps
            merged.update({key: value for key, value in result.items() if key != "capabilities"})
            return merged
        return result

    resolved = visit(name, ())
    if not resolved.get("capabilities"):
        raise BundleInputError(f"profile has no capabilities: {name}")
    return {"name": name, **resolved}
