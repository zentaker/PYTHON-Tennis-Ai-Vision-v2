"""Validation for manifest-driven detector/tracker/pose bundles."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class ModelBundleError(ValueError):
    """Raised when a model bundle is incomplete or unsafe to execute."""


def _relative_path(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ModelBundleError(f"{name} must be a non-empty relative path")
    return value


def load_model_bundle(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ModelBundleError(f"model bundle not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ModelBundleError(f"model bundle is invalid JSON: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != "1.0":
        raise ModelBundleError("model bundle schema_version must be 1.0")
    for component in ("detector", "pose"):
        section = payload.get(component)
        if not isinstance(section, dict):
            raise ModelBundleError(f"model bundle missing {component} section")
        _relative_path(section.get("config"), f"{component}.config")
        _relative_path(section.get("checkpoint"), f"{component}.checkpoint")
        checksum = section.get("checksum_sha256")
        if checksum is not None and (
            not isinstance(checksum, str)
            or len(checksum) != 64
            or any(c not in "0123456789abcdef" for c in checksum)
        ):
            raise ModelBundleError(f"{component}.checksum_sha256 must be lowercase SHA-256 or null")
        if not isinstance(section.get("input_size"), list) or len(section["input_size"]) != 2:
            raise ModelBundleError(f"{component}.input_size must contain width and height")
    tracker = payload.get("tracker")
    if not isinstance(tracker, dict) or not tracker.get("implementation"):
        raise ModelBundleError("model bundle tracker implementation is required")
    runtime = payload.get("runtime")
    if not isinstance(runtime, dict) or runtime.get("device") not in {"cpu", "cuda", "auto"}:
        raise ModelBundleError("runtime.device must be cpu, cuda or auto")
    _relative_path(runtime.get("model_cache_path"), "runtime.model_cache_path")
    return payload


def resolve_model_path(models_dir: Path, bundle_path: str) -> Path:
    """Resolve a manifest path under a model mount and prevent path traversal."""
    root = models_dir.resolve()
    candidate = (root / bundle_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ModelBundleError(f"model path escapes models directory: {bundle_path}")
    return candidate


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
