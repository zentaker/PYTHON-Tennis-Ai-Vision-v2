from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_lightning_config_is_free_and_ten_frame_guarded() -> None:
    config = json.loads((ROOT / "config/providers/lightning_p1_smoke.json").read_text())
    assert config["subscription_cost_usd"] == 0
    assert config["included_monthly_credits"] == 15
    assert config["credit_value_usd"] == 1
    assert config["payment_method_required"] is False
    assert config["phone_verification_required"] is True
    assert config["max_out_of_pocket_approved_usd"] == 0
    assert config["max_frames"] == 10
    assert config["max_gpu_count"] == 1
    assert config["sdk_gate_status"] == "SDK_API_SHAPE_VALIDATED"
    assert config["provider_status"] == "READY_FOR_LIGHTNING_ACCOUNT_REVIEW"
    assert config["account_status"] == "NOT_CREATED"
    assert config["payment_method_account_verified"] is False
    assert config["credits_status"] == "NOT_VERIFIED"
    assert config["gpu_status"] == "NOT_VERIFIED"
    assert config["remote_execution_authorized"] is False


def test_lightning_sdk_is_concretely_pinned_and_gate_is_offline() -> None:
    requirements = (ROOT / "infrastructure/lightning/requirements-lightning.txt").read_text()
    assert requirements.strip() == "lightning-sdk==2026.7.9.post0"
    source = (ROOT / "scripts/lightning_sdk_gate.py").read_text()
    assert "remote_calls\": 0" in source
    assert "resources_created\": 0" in source
    assert "LIGHTNING_API_KEY" in source
    assert "Studio.upload_file" in source
    assert "Studio.download_file" in source
    assert "Job.logs" in source
    assert "Job.stop" in source
    assert "resources_created\": 0" in source


def test_modal_is_rejected_and_runtime_call_record_is_ignored() -> None:
    modal = json.loads((ROOT / "config/providers/modal_p1_smoke.json").read_text())
    assert modal["adapter_status"] == "VALIDATED_OFFLINE"
    assert modal["provider_status"] == "REJECTED_PAYMENT_METHOD_POLICY"
    assert modal["remote_execution_authorized"] is False
    assert modal["rejection_reason"] == "Modal requires a payment method on file"
    gitignore = (ROOT / ".gitignore").read_text()
    for pattern in (".modal_smoke/", ".modal_smoke_approval.json", ".modal_smoke_function_call.json", "outputs/", "*.pth", "*.mp4"):
        assert pattern in gitignore
