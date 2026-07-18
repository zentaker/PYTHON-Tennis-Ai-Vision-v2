from __future__ import annotations

import json
from pathlib import Path

from infrastructure.modal import p1_smoke
from scripts.audit_modal_cleanup import audit


ROOT = Path(__file__).resolve().parents[1]


def test_modal_adapter_is_import_safe_and_core_stays_provider_neutral() -> None:
    contract = p1_smoke.dry_run()
    assert contract["status"] == "READY_FOR_MODAL_AUTH"
    assert contract["remote_calls"] == 0
    assert p1_smoke.GPU_FALLBACK == ["L4", "A10", "T4"]


def test_modal_contract_uses_one_dockerfile_and_guarded_limits() -> None:
    config = json.loads((ROOT / "config/providers/modal_p1_smoke.json").read_text())
    assert config["max_execution_seconds"] == 900
    assert config["retries"] == 0
    assert config["max_frames"] == 10
    assert config["max_gpu_count"] == 1
    assert config["deployed"] is False
    assert config["detached"] is False
    assert "context_dir=ROOT" in p1_smoke.dry_run()["image_source"]


def test_smoke_package_has_exactly_ten_verified_frames() -> None:
    package_path = ROOT / ".modal_smoke/nivel_a2_01/inputs/p1_smoke_manifest.json"
    package = p1_smoke.verify_package(package_path)
    assert package["frame_count"] == 10
    assert len(package["frames"]) == 10
    assert package["frames"][1]["event_ids"] == ["ev_001"]
    assert package["frames"][4]["event_ids"] == ["ev_003"]


def test_cleanup_audit_is_local_only(tmp_path: Path) -> None:
    report = audit(tmp_path)
    assert report["remote_commands_not_executed"] is True
    assert report["local_outputs_downloaded"] is False
    assert report["persistent_volume_names"] == ["tennisai-p1-assets", "tennisai-p1-results"]


def test_modal_sdk_contract_is_pinned_and_safe() -> None:
    requirement = (ROOT / "infrastructure/modal/requirements-modal.txt").read_text()
    assert requirement.strip() == "modal==1.5.2"
    source = (ROOT / "infrastructure/modal/p1_smoke.py").read_text()
    assert "Image.from_dockerfile(str(DOCKERFILE), context_dir=ROOT)" in source
    assert "batch_upload(force=True)" in source
    assert "assets.commit()" in source
    assert "results.commit()" in source
    assert "results.reload()" in source
    assert "current_input_id()" in source
    assert "call.object_id" in source
    assert "call.cancel()" in source
    assert "app._p1_run_smoke" not in source
    assert '"keypoint_count": 133' not in source


def test_modal_cost_guards_are_explicit() -> None:
    config = json.loads((ROOT / "config/providers/modal_p1_smoke.json").read_text())
    assert config["subscription_cost_usd"] == 0
    assert config["included_monthly_credits_usd"] == 30
    assert config["expected_charge_usd"] is None
    assert config["max_out_of_pocket_approved_usd"] == 0
    assert config["requires_free_credit"] is True
    assert config["pricing_status"] == "VERIFIED_STATIC"
    assert config["authentication_status"] == "NOT_CONFIGURED"
    assert config["billing_status"] == "NOT_CONFIGURED"
    assert config["workspace_budget_status"] == "NOT_CONFIGURED"
