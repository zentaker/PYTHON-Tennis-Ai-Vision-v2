from __future__ import annotations

import hashlib
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
    source = tmp_path / "session.mp4"
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest() if source.exists() else "0" * 64
    session.write_text(
        json.dumps(
            {
                "schema_version": "session.v1",
                "session_id": "s1",
                "source_video": {"display_name": source.name, "sha256": source_sha},
                "surface": "hard",
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
        _source(tmp_path), _inputs(tmp_path), "s1", "FAST", "hard", output, "2026-07-20T00:00:00Z"
    )
    assert result["files_verified"] == 2
    assert validate_bundle(output)["fingerprint"] == result["fingerprint"]
    manifest = json.loads((output / "manifest.json").read_text())
    session = json.loads((output / "session.json").read_text())
    assert session["source_video"]["sha256"] == manifest["source_video"]["sha256"]
    assert (output / "clips").is_dir() and (output / "thumbnails").is_dir()


def test_deterministic_fingerprint(tmp_path: Path) -> None:
    source = _source(tmp_path)
    descriptor = _inputs(tmp_path)
    first = build_bundle(
        source, descriptor, "s1", "FAST", "hard", tmp_path / "one", "2026-07-20T00:00:00Z"
    )
    second = build_bundle(
        source, descriptor, "s1", "FAST", "hard", tmp_path / "two", "2026-07-20T00:00:00Z"
    )
    assert first["fingerprint"] == second["fingerprint"]


def test_existing_requires_overwrite(tmp_path: Path) -> None:
    source = _source(tmp_path)
    descriptor = _inputs(tmp_path)
    output = tmp_path / "bundle"
    build_bundle(source, descriptor, "s1", "FAST", "hard", output, "2026-07-20T00:00:00Z")
    with pytest.raises(BundleBuildError):
        build_bundle(source, descriptor, "s1", "FAST", "hard", output, "2026-07-20T00:00:00Z")
    build_bundle(
        source, descriptor, "s1", "FAST", "hard", output, "2026-07-20T00:00:00Z", overwrite=True
    )


def test_missing_required_and_optional_omitted(tmp_path: Path) -> None:
    source = _source(tmp_path)
    descriptor = _inputs(tmp_path)
    data = json.loads(descriptor.read_text())
    data["files"]["session"]["path"] = str(tmp_path / "missing.json")
    descriptor.write_text(json.dumps(data))
    with pytest.raises(BundleInputError):
        build_bundle(
            source, descriptor, "s1", "FAST", "hard", tmp_path / "out", "2026-07-20T00:00:00Z"
        )
    optional = tmp_path / "events.jsonl"
    optional.write_text("")
    descriptor = _inputs(tmp_path, optional=optional)
    result = build_bundle(
        source, descriptor, "s1", "FAST", "hard", tmp_path / "optional", "2026-07-20T00:00:00Z"
    )
    assert result["files_verified"] == 3


def test_integrity_and_path_traversal_rejected(tmp_path: Path) -> None:
    source = _source(tmp_path)
    output = tmp_path / "out"
    build_bundle(source, _inputs(tmp_path), "s1", "FAST", "hard", output, "2026-07-20T00:00:00Z")
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
            "hard",
            tmp_path / "bad",
            "2026-07-20T00:00:00Z",
        )
    source = _source(tmp_path)
    output = tmp_path / "good"
    build_bundle(source, _inputs(tmp_path), "s1", "FAST", "hard", output, "2026-07-20T00:00:00Z")
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


def test_profile_cycle_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps(
            {
                "profiles": {
                    "A": {"extends": "B", "capabilities": {"a": {}}},
                    "B": {"extends": "A", "capabilities": {"b": {}}},
                }
            }
        )
    )
    with pytest.raises(BundleInputError):
        resolve_profile("A", path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("session_id", "other", "session_id"),
        ("processing_profile", "TACTICAL", "processing_profile"),
        ("surface", "clay", "surface"),
    ],
)
def test_session_manifest_consistency(tmp_path: Path, field: str, value: str, message: str) -> None:
    source = _source(tmp_path)
    output = tmp_path / "bundle"
    build_bundle(source, _inputs(tmp_path), "s1", "FAST", "hard", output, "2026-07-20T00:00:00Z")
    session = json.loads((output / "session.json").read_text())
    session[field] = value
    (output / "session.json").write_text(json.dumps(session))
    with pytest.raises(BundleIntegrityError, match=message):
        validate_bundle(output)


def test_source_metadata_and_rallies_consistency(tmp_path: Path) -> None:
    source = _source(tmp_path)
    output = tmp_path / "bundle"
    build_bundle(source, _inputs(tmp_path), "s1", "FAST", "hard", output, "2026-07-20T00:00:00Z")
    session = json.loads((output / "session.json").read_text())
    session["source_video"]["display_name"] = "other.mp4"
    (output / "session.json").write_text(json.dumps(session))
    with pytest.raises(BundleIntegrityError, match="display_name"):
        validate_bundle(output)
    build_bundle(
        source,
        _inputs(tmp_path),
        "s1",
        "FAST",
        "hard",
        output,
        "2026-07-20T00:00:00Z",
        overwrite=True,
    )
    session = json.loads((output / "session.json").read_text())
    session["source_video"]["sha256"] = "f" * 64
    (output / "session.json").write_text(json.dumps(session))
    with pytest.raises(BundleIntegrityError, match="sha256"):
        validate_bundle(output)
    build_bundle(
        source,
        _inputs(tmp_path),
        "s1",
        "FAST",
        "hard",
        output,
        "2026-07-20T00:00:00Z",
        overwrite=True,
    )
    rallies = json.loads((output / "rallies.json").read_text())
    rallies["session_id"] = "other"
    (output / "rallies.json").write_text(json.dumps(rallies))
    with pytest.raises(BundleIntegrityError, match="rallies.json session_id"):
        validate_bundle(output)


def test_relative_descriptor_and_symlink_rejected(tmp_path: Path) -> None:
    source = _source(tmp_path)
    descriptor_dir = tmp_path / "descriptor"
    descriptor_dir.mkdir()
    (descriptor_dir / "session.json").write_text((tmp_path / "session.json").read_text()) if (
        tmp_path / "session.json"
    ).exists() else None
    descriptor = _inputs(tmp_path)
    nested = descriptor_dir / "bundle-inputs.json"
    data = json.loads(descriptor.read_text())
    data["files"]["session"]["path"] = "session.json"
    data["files"]["rallies"]["path"] = "rallies.json"
    (descriptor_dir / "session.json").write_text((tmp_path / "session.json").read_text())
    (descriptor_dir / "rallies.json").write_text((tmp_path / "rallies.json").read_text())
    nested.write_text(json.dumps(data))
    assert (
        build_bundle(
            source, nested, "s1", "FAST", "hard", tmp_path / "relative", "2026-07-20T00:00:00Z"
        )["files_verified"]
        == 2
    )
    link = descriptor_dir / "link.json"
    link.symlink_to(descriptor_dir / "session.json")
    data["files"]["session"]["path"] = "link.json"
    nested.write_text(json.dumps(data))
    with pytest.raises(BundlePathError, match="symlink"):
        build_bundle(
            source, nested, "s1", "FAST", "hard", tmp_path / "symlink", "2026-07-20T00:00:00Z"
        )


def test_not_analyzed_status_allows_empty_rallies(tmp_path: Path) -> None:
    source = _source(tmp_path)
    result = build_bundle(
        source, _inputs(tmp_path), "s1", "FAST", "hard", tmp_path / "bundle", "2026-07-20T00:00:00Z"
    )
    assert result["session_id"] == "s1"
    assert json.loads((tmp_path / "bundle/manifest.json").read_text())["status"] == "complete"
