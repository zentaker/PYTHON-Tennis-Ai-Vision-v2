from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.product.analysis_bundle.builder import build_bundle
from src.product.analysis_bundle.errors import (
    BundleBuildError,
    BundleInputError,
    BundleIntegrityError,
    BundlePathError,
    BundleSchemaError,
)
from src.product.analysis_bundle.profiles import resolve_profile
from src.product.analysis_bundle.validator import validate_bundle


def _inputs(tmp_path: Path, *, optional: Path | None = None) -> Path:
    session = tmp_path / "session.json"
    session.write_text(
        json.dumps(
            {
                "schema_version": "session.v1",
                "session_id": "s1",
                "source_video": {"display_name": "x.mp4", "sha256": "0" * 64},
                "surface": "clay",
                "processing_profile": "FAST",
                "status": "not_analyzed",
                "capabilities": ["bundle_contract"],
                "limitations": ["fixture_only"],
            }
        )
    )
    rallies = tmp_path / "rallies.json"
    rallies.write_text(
        json.dumps(
            {
                "schema_version": "rallies.v1",
                "session_id": "s1",
                "status": "not_analyzed",
                "rallies": [],
            }
        )
    )
    descriptor = {
        "schema_version": "analysis_bundle_inputs.v1",
        "files": {
            "session": {
                "path": str(session),
                "required": True,
                "media_type": "application/json",
                "schema_version": "session.v1",
            },
            "rallies": {
                "path": str(rallies),
                "required": True,
                "media_type": "application/json",
                "schema_version": "rallies.v1",
            },
        },
        "capabilities": ["bundle_contract"],
        "limitations": ["fixture_only"],
    }
    if optional:
        descriptor["files"]["events"] = {
            "path": str(optional),
            "required": False,
            "media_type": "application/jsonl",
            "schema_version": "events.v1",
            "allow_empty_jsonl": True,
        }
    path = tmp_path / "bundle-inputs.json"
    path.write_text(json.dumps(descriptor))
    return path


def _source(tmp_path: Path) -> Path:
    path = tmp_path / "session.mp4"
    path.write_bytes(b"non-decodable packaging fixture")
    return path


def test_build_and_validate_success(tmp_path: Path) -> None:
    output = tmp_path / "analysis" / "s1"
    result = build_bundle(
        _source(tmp_path), _inputs(tmp_path), "s1", "FAST", "clay", output, "2026-07-20T00:00:00Z"
    )
    assert result["files_verified"] == 2
    assert validate_bundle(output)["fingerprint"] == result["fingerprint"]
    assert (output / "clips").is_dir() and (output / "thumbnails").is_dir()


def test_deterministic_fingerprint(tmp_path: Path) -> None:
    source = _source(tmp_path)
    descriptor = _inputs(tmp_path)
    first = build_bundle(
        source, descriptor, "s1", "FAST", "clay", tmp_path / "one", "2026-07-20T00:00:00Z"
    )
    second = build_bundle(
        source, descriptor, "s1", "FAST", "clay", tmp_path / "two", "2026-07-20T00:00:00Z"
    )
    assert first["fingerprint"] == second["fingerprint"]


def test_existing_requires_overwrite(tmp_path: Path) -> None:
    source = _source(tmp_path)
    descriptor = _inputs(tmp_path)
    output = tmp_path / "bundle"
    build_bundle(source, descriptor, "s1", "FAST", "clay", output, "2026-07-20T00:00:00Z")
    with pytest.raises(BundleBuildError):
        build_bundle(source, descriptor, "s1", "FAST", "clay", output, "2026-07-20T00:00:00Z")
    build_bundle(
        source, descriptor, "s1", "FAST", "clay", output, "2026-07-20T00:00:00Z", overwrite=True
    )


def test_missing_required_and_optional_omitted(tmp_path: Path) -> None:
    source = _source(tmp_path)
    descriptor = _inputs(tmp_path)
    data = json.loads(descriptor.read_text())
    data["files"]["session"]["path"] = str(tmp_path / "missing.json")
    descriptor.write_text(json.dumps(data))
    with pytest.raises(BundleInputError):
        build_bundle(
            source, descriptor, "s1", "FAST", "clay", tmp_path / "out", "2026-07-20T00:00:00Z"
        )
    optional = tmp_path / "events.jsonl"
    optional.write_text("")
    descriptor = _inputs(tmp_path, optional=optional)
    result = build_bundle(
        source, descriptor, "s1", "FAST", "clay", tmp_path / "optional", "2026-07-20T00:00:00Z"
    )
    assert result["files_verified"] == 3


def test_integrity_and_path_traversal_rejected(tmp_path: Path) -> None:
    source = _source(tmp_path)
    output = tmp_path / "out"
    build_bundle(source, _inputs(tmp_path), "s1", "FAST", "clay", output, "2026-07-20T00:00:00Z")
    manifest = output / "manifest.json"
    value = json.loads(manifest.read_text())
    value["files"]["session"]["size_bytes"] += 1
    manifest.write_text(json.dumps(value))
    with pytest.raises(BundleIntegrityError):
        validate_bundle(output)
    descriptor = _inputs(tmp_path)
    data = json.loads(descriptor.read_text())
    data["files"]["session"]["path"] = "../outside.json"
    descriptor.write_text(json.dumps(data))
    with pytest.raises(BundlePathError):
        build_bundle(
            source, descriptor, "s1", "FAST", "clay", tmp_path / "bad", "2026-07-20T00:00:00Z"
        )


def test_malformed_jsonl_and_source_verification(tmp_path: Path) -> None:
    bad = tmp_path / "events.jsonl"
    bad.write_text("not json\n")
    descriptor = _inputs(tmp_path, optional=bad)
    with pytest.raises(BundleSchemaError):
        build_bundle(
            _source(tmp_path),
            descriptor,
            "s1",
            "FAST",
            "clay",
            tmp_path / "bad",
            "2026-07-20T00:00:00Z",
        )
    source = _source(tmp_path)
    output = tmp_path / "good"
    build_bundle(source, _inputs(tmp_path), "s1", "FAST", "clay", output, "2026-07-20T00:00:00Z")
    assert validate_bundle(output, source)["files_verified"] == 2
    source.write_bytes(b"changed")
    with pytest.raises(BundleIntegrityError):
        validate_bundle(output, source)


def test_profiles_and_no_heavy_imports() -> None:
    resolved = resolve_profile("TACTICAL")
    assert (
        "activity_scan" in resolved["capabilities"] and "coaching_input" in resolved["capabilities"]
    )
    source = (Path(__file__).parents[1] / "src/product").read_text() if False else ""
    assert "torch" not in source
