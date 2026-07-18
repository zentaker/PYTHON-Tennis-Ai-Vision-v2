import json
from pathlib import Path

from src.analytics.contracts import ContactMode, HittingHand, SpinFamily, StrokeSide, TacticalShape


def test_taxonomy_config_matches_enums_and_unknown_is_universal():
    data = json.loads(Path("config/analytics/stroke_taxonomy_v1.json").read_text())
    expected = {
        "stroke_side": StrokeSide,
        "contact_mode": ContactMode,
        "spin_family": SpinFamily,
        "tactical_shape": TacticalShape,
        "hitting_hand": HittingHand,
    }
    for name, enum in expected.items():
        assert data[name] == [item.value for item in enum]
        assert "unknown" in data[name]


def test_json_schemas_are_valid_json_with_required_identity():
    for path in Path("config/analytics").glob("*.json"):
        payload = json.loads(path.read_text())
        assert isinstance(payload, dict)
