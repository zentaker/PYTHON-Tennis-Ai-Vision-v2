from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

from .checksums import bundle_fingerprint, sha256_file
from .errors import BundleBuildError, BundleInputError, BundlePathError, BundleSchemaError
from .profiles import resolve_profile
from .validator import CONTRACT_FILES, _parse_file, validate_bundle

ROOT = Path(__file__).parents[3]
INPUT_SCHEMA = ROOT / "config/product/analysis_bundle_inputs.schema.json"
MEDIA_EXTENSIONS = {".json": "application/json", ".jsonl": "application/jsonl"}


def _load_descriptor(path: Path) -> dict[str, Any]:
    try:
        descriptor = json.loads(path.read_text())
        jsonschema.validate(descriptor, json.loads(INPUT_SCHEMA.read_text()))
    except (OSError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
        raise BundleInputError(f"invalid input descriptor: {path}") from exc
    unknown = set(descriptor["files"]) - {Path(name).stem for name in CONTRACT_FILES}
    if unknown:
        raise BundleInputError(f"unknown logical input(s): {', '.join(sorted(unknown))}")
    return descriptor


def _validate_source(source: Path, output: Path) -> None:
    source = source.resolve()
    if not source.is_file() or source.suffix.lower() not in {".mp4", ".mov"}:
        raise BundleInputError("source video must be an existing .mp4 or .mov file")
    if output.resolve() == source:
        raise BundlePathError("output cannot be the source video")


def _copy_inputs(descriptor: dict[str, Any], temp: Path) -> tuple[dict[str, Any], dict[str, str]]:
    files: dict[str, Any] = {}
    checksums: dict[str, str] = {}
    for logical, spec in descriptor["files"].items():
        path = Path(spec["path"]).expanduser()
        if not path.is_absolute() and ".." in path.parts:
            raise BundlePathError(f"input path traversal: {logical}")
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        if not path.exists() or not path.is_file():
            if spec["required"]:
                raise BundleInputError(f"required input missing: {logical}")
            continue
        if path.is_symlink():
            raise BundlePathError(f"unsafe input symlink: {logical}")
        suffix = path.suffix.lower()
        if suffix not in MEDIA_EXTENSIONS:
            raise BundleInputError(f"unsupported input media type: {logical}")
        destination = f"{logical}{suffix}"
        destination_path = temp / destination
        shutil.copy2(path, destination_path)
        if suffix == ".json" and path.stat().st_size == 0:
            raise BundleSchemaError(f"empty JSON input: {logical}")
        if (
            suffix == ".jsonl"
            and path.stat().st_size == 0
            and not spec.get("allow_empty_jsonl", False)
        ):
            raise BundleSchemaError(f"empty JSONL input: {logical}")
        _parse_file(destination_path, spec.get("allow_empty_jsonl", False))
        files[logical] = {
            "path": destination,
            "required": spec["required"],
            "producer": "existing_core_output",
            "consumer": "core_bundle_and_web",
            "media_type": spec["media_type"],
            "schema_version": spec["schema_version"],
            "allow_empty_jsonl": bool(spec.get("allow_empty_jsonl", False)),
        }
        checksums[destination] = sha256_file(destination_path)
    return files, checksums


def build_bundle(
    source_video: Path,
    inputs: Path,
    session_id: str,
    profile: str,
    surface: str,
    output: Path,
    created_at: str | None = None,
    core_version: str = "0.1.0",
    overwrite: bool = False,
) -> dict[str, Any]:
    if not session_id or any(
        char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        for char in session_id
    ):
        raise BundleInputError("session-id contains unsafe characters")
    resolve_profile(profile)
    _validate_source(source_video, output)
    descriptor = _load_descriptor(inputs)
    if output.exists() and not overwrite:
        raise BundleBuildError(f"bundle already exists: {output}")
    if created_at is None:
        created_at = (
            datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
    try:
        datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BundleInputError("created-at must be RFC3339") from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
    try:
        (temp / "clips").mkdir()
        (temp / "thumbnails").mkdir()
        files, checksums = _copy_inputs(descriptor, temp)
        source_path = Path(source_video).resolve()
        manifest_files = {}
        for logical, entry in files.items():
            size = (temp / entry["path"]).stat().st_size
            manifest_files[logical] = {**entry, "size_bytes": size}
        source_sha = sha256_file(source_path)
        manifest: dict[str, Any] = {
            "schema_version": "analysis_bundle.v1",
            "core_version": core_version,
            "session_id": session_id,
            "created_at": created_at,
            "source_video": {
                "display_name": source_path.name,
                "sha256": source_sha,
                "format": source_path.suffix.lower().lstrip("."),
                "size_bytes": source_path.stat().st_size,
                "storage": "external",
            },
            "processing_profile": profile,
            "surface": surface,
            "files": manifest_files,
            "capabilities": descriptor["capabilities"],
            "limitations": descriptor["limitations"] + ["stage0b_packages_existing_outputs_only"],
            "checksums": checksums,
            "status": "complete",
        }
        manifest["bundle_fingerprint"] = bundle_fingerprint(manifest, checksums, source_sha)
        (temp / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        validate_bundle(temp)
        backup = None
        if output.exists():
            if not overwrite:
                raise BundleBuildError(f"bundle already exists: {output}")
            backup = output.with_name(f".{output.name}.previous-{os.getpid()}")
            os.replace(output, backup)
        try:
            os.replace(temp, output)
        except Exception:
            if backup is not None and backup.exists():
                os.replace(backup, output)
            raise
        if backup is not None and backup.exists():
            shutil.rmtree(backup) if backup.is_dir() else backup.unlink()
        return validate_bundle(output)
    except Exception:
        if temp.exists():
            shutil.rmtree(temp)
        raise
