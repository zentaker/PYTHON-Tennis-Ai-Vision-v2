from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).parents[1]


def test_analysis_bundle_fixture_matches_v1_schema() -> None:
    schema = json.loads((ROOT / "config/product/analysis_bundle_manifest.schema.json").read_text())
    fixture = json.loads((ROOT / "tests/fixtures/product/analysis_bundle_v1/manifest.json").read_text())
    jsonschema.validate(fixture, schema)


def test_processing_profiles_are_complete() -> None:
    profiles = json.loads((ROOT / "config/product/processing_profiles_v1.json").read_text())["profiles"]
    assert set(profiles) == {"FAST", "STANDARD", "TACTICAL"}
    assert profiles["STANDARD"]["extends"] == "FAST"
    assert profiles["TACTICAL"]["extends"] == "STANDARD"
