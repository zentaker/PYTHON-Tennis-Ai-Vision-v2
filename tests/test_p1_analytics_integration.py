from __future__ import annotations

import ast
import importlib
import json
import sys
from pathlib import Path

import pytest

from src.analytics.adapters.stage4_events import adapt_stage4_event
from src.analytics.contracts import AnalyticsEventInput, BallKinematics, ClassifiedStroke, StrokeAnalyticsRecord
from src.analytics.schema_validation import synthetic_kinematics_states, validators

ROOT = Path(__file__).resolve().parents[1]
HEAVY_MODULES = ("lightning", "modal", "torch", "mmdet", "mmpose")


def test_packages_coexist_without_provider_imports_or_cycle() -> None:
    before = set(sys.modules)
    player = importlib.import_module("src.player_perception")
    analytics = importlib.import_module("src.analytics")
    loaded = set(sys.modules) - before
    assert player is not None and analytics is not None
    assert not any(name == prefix or name.startswith(prefix + ".") for name in loaded for prefix in HEAVY_MODULES)

    for path in (ROOT / "src/player_perception").rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        assert not any(
            (isinstance(node, ast.ImportFrom) and (node.module or "").startswith("src.analytics"))
            or (isinstance(node, ast.Import) and any(alias.name.startswith("src.analytics") for alias in node.names))
            for node in imports
        )


@pytest.mark.parametrize("kinematics", synthetic_kinematics_states())
def test_record_serialization_validates_all_kinematics_states(kinematics: BallKinematics) -> None:
    _, stroke_validator = validators()
    record = StrokeAnalyticsRecord(
        "1.0", AnalyticsEventInput(f"synthetic-{kinematics.status}", 0.0), ClassifiedStroke(), kinematics
    )
    stroke_validator.validate(record.to_dict())


def test_stage4_adapter_remains_conservative() -> None:
    result = adapt_stage4_event({"shot_type": "slice"})
    assert result.spin_family == "slice"
    assert result.stroke_side == result.contact_mode == "unknown"


def test_near_far_identity_contract_is_compatible() -> None:
    from src.analytics.contracts import PlayerContextSample
    from src.player_perception.schemas import PlayerTrack

    assert {PlayerContextSample(0.0, "1", identity).identity for identity in ("near", "far")} == {"near", "far"}
    annotations = PlayerTrack.__annotations__
    assert annotations["identity"] in ("str", str)


def test_manifest_and_provider_gates_remain_offline() -> None:
    manifest = json.loads((ROOT / "config/integration/p1_analytics_integration.json").read_text())
    lightning = json.loads((ROOT / "config/providers/lightning_p1_smoke.json").read_text())
    assert manifest["common_base_sha"] == "e81949bc01cbd2adfca12bd5b3a6a28c3e792fea"
    assert manifest["p1_source_sha"] == "a15b91fadb2b0b1badb6ce1009896458b3dac718"
    assert manifest["analytics_source_sha"] == "bab71a7b49e2b8de7aeccef61eb9836a3722f56e"
    assert lightning["account_status"] == "NOT_CREATED"
    assert lightning["remote_execution_authorized"] is False
    assert manifest["cloud_calls"] == manifest["gpu_calls"] == manifest["spend_usd"] == 0
    assert manifest["real_video_inference"] is manifest["functional_data_wiring"] is False
