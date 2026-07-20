from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from .checksums import bundle_fingerprint, sha256_file
from .errors import BundleIntegrityError, BundlePathError, BundleSchemaError

ROOT = Path(__file__).parents[3]
CONTRACT_FILES = {
    "session.json",
    "rallies.json",
    "events.jsonl",
    "ball_track.jsonl",
    "player_tracks.jsonl",
    "poses.jsonl",
    "court_map.json",
    "metrics.json",
    "tactical_patterns.json",
    "coaching_input.json",
}


def safe_relative(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise BundlePathError(f"unsafe bundle path: {path}")
    return candidate


def _schema_validate(value: Any, schema_path: Path) -> None:
    try:
        jsonschema.validate(value, json.loads(schema_path.read_text()))
    except jsonschema.ValidationError as exc:
        raise BundleSchemaError(f"{schema_path.name}: {exc.message}") from exc


def _parse_file(path: Path, allow_empty_jsonl: bool = False) -> Any:
    if path.stat().st_size == 0:
        if path.suffix == ".jsonl" and allow_empty_jsonl:
            return None
        raise BundleSchemaError(f"empty file is not valid: {path.name}")
    if path.suffix == ".json":
        try:
            value = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise BundleSchemaError(f"malformed JSON: {path.name}") from exc
        if path.name == "session.json":
            _schema_validate(value, ROOT / "config/product/session_v1.schema.json")
        elif path.name == "rallies.json":
            _schema_validate(value, ROOT / "config/product/rallies_v1.schema.json")
        return value
    elif path.suffix == ".jsonl":
        for number, line in enumerate(path.read_text().splitlines(), 1):
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                raise BundleSchemaError(f"malformed JSONL: {path.name}:{number}") from exc
    return None


def validate_bundle(bundle: Path, verify_source: Path | None = None) -> dict[str, Any]:
    bundle = bundle.resolve()
    manifest_path = bundle / "manifest.json"
    if not manifest_path.is_file():
        raise BundleSchemaError("manifest.json is missing")
    try:
        manifest = json.loads(manifest_path.read_text())
        _schema_validate(manifest, ROOT / "config/product/analysis_bundle_manifest.schema.json")
    except json.JSONDecodeError as exc:
        raise BundleSchemaError("manifest JSON is malformed") from exc
    if not manifest["capabilities"] or not manifest["limitations"]:
        raise BundleSchemaError("capabilities and limitations must be non-empty")
    checksums: dict[str, str] = {}
    parsed_files: dict[str, Any] = {}
    target_paths: dict[str, Path] = {}
    files_verified = 0
    for logical, entry in manifest["files"].items():
        relative = safe_relative(entry["path"])
        target = (bundle / relative).resolve()
        if bundle not in target.parents and target != bundle:
            raise BundlePathError(f"file escapes bundle: {entry['path']}")
        if not target.is_file():
            if entry["required"]:
                raise BundleIntegrityError(f"required file missing: {entry['path']}")
            continue
        parsed = _parse_file(target, bool(entry.get("allow_empty_jsonl", False)))
        parsed_files[logical] = parsed
        target_paths[logical] = target
    manifest_session = parsed_files.get("session")
    if manifest_session is not None:
        expected = manifest["session_id"]
        if manifest_session["session_id"] != expected:
            raise BundleIntegrityError("session.json session_id does not match manifest.json")
        if manifest_session["processing_profile"] != manifest["processing_profile"]:
            raise BundleIntegrityError(
                "session.json processing_profile does not match manifest.json"
            )
        if manifest_session["surface"] != manifest["surface"]:
            raise BundleIntegrityError("session.json surface does not match manifest.json")
        source = manifest_session["source_video"]
        manifest_source = manifest["source_video"]
        if source["display_name"] != manifest_source["display_name"]:
            raise BundleIntegrityError(
                "session.json source_video.display_name does not match manifest.json"
            )
        if source["sha256"].lower() != manifest_source["sha256"].lower():
            raise BundleIntegrityError(
                "session.json source_video.sha256 does not match manifest.json"
            )
    manifest_rallies = parsed_files.get("rallies")
    if manifest_rallies is not None and manifest_rallies["session_id"] != manifest["session_id"]:
        raise BundleIntegrityError("rallies.json session_id does not match manifest.json")
    for logical, target in target_paths.items():
        entry = manifest["files"][logical]
        size = target.stat().st_size
        if entry.get("size_bytes") != size:
            raise BundleIntegrityError(f"size mismatch: {entry['path']}")
        digest = sha256_file(target)
        if manifest["checksums"].get(entry["path"]) != digest:
            raise BundleIntegrityError(f"checksum mismatch: {entry['path']}")
        checksums[entry["path"]] = digest
        files_verified += 1
    for directory in ("clips", "thumbnails"):
        if not (bundle / directory).is_dir():
            raise BundleIntegrityError(f"required directory missing: {directory}")
    without = dict(manifest)
    fingerprint = without.pop("bundle_fingerprint", None)
    expected = bundle_fingerprint(without, checksums, manifest["source_video"]["sha256"])
    if fingerprint != expected:
        raise BundleIntegrityError("bundle fingerprint mismatch")
    if verify_source is not None:
        if sha256_file(verify_source.resolve()) != manifest["source_video"]["sha256"]:
            raise BundleIntegrityError("source video checksum mismatch")
    return {
        "session_id": manifest["session_id"],
        "fingerprint": expected,
        "files_verified": files_verified,
    }
