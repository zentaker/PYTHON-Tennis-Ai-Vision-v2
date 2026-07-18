#!/usr/bin/env python3
"""Offline API-shape gate for the pinned Lightning AI SDK.

The SDK is imported and real Studio/Job objects are represented in memory. All
network transports are blocked before any object API is touched; no account,
resource, endpoint or credential is used.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import socket
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/providers/lightning_p1_smoke.json"


def _block_network() -> list[tuple[Any, str, Any]]:
    import requests
    import urllib3

    patches: list[tuple[Any, str, Any]] = []

    def blocked(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("offline Lightning SDK gate attempted a network call")

    targets = [
        (requests.api, "request"),
        (requests.sessions.Session, "request"),
        (urllib3.connectionpool.HTTPConnectionPool, "urlopen"),
        (urllib3.connectionpool.HTTPSConnectionPool, "urlopen"),
        (socket, "create_connection"),
    ]
    for owner, name in targets:
        original = getattr(owner, name)
        setattr(owner, name, blocked)
        patches.append((owner, name, original))
    return patches


def _restore_network(patches: list[tuple[Any, str, Any]]) -> None:
    for owner, name, original in patches:
        setattr(owner, name, original)


def _check_config() -> dict[str, Any]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    expected = {
        "provider": "lightning-ai",
        "plan": "Free",
        "sdk_gate_status": "SDK_API_SHAPE_VALIDATED",
        "provider_status": "READY_FOR_LIGHTNING_ACCOUNT_REVIEW",
        "subscription_cost_usd": 0,
        "included_monthly_credits": 15,
        "credit_value_usd": 1,
        "payment_method_required": False,
        "payment_method_required_static": False,
        "payment_method_account_verified": False,
        "phone_verification_required": True,
        "phone_verification_status": "NOT_VERIFIED",
        "max_out_of_pocket_approved_usd": 0,
        "max_frames": 10,
        "max_gpu_count": 1,
        "preferred_gpu_order": ["T4", "L4"],
        "account_status": "NOT_CREATED",
        "authentication_status": "NOT_CONFIGURED",
        "credits_status": "NOT_VERIFIED",
        "gpu_status": "NOT_VERIFIED",
        "remote_execution_authorized": False,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise RuntimeError(f"Lightning provider config mismatch for {key}: {config.get(key)!r}")
    return config


def run() -> dict[str, Any]:
    credential_names = ("LIGHTNING_USER_ID", "LIGHTNING_API_KEY", "LIGHTNING_SANDBOX_API_KEY")
    if any(name in os.environ for name in credential_names):
        raise RuntimeError("Lightning credentials must not be present in the offline gate")
    import lightning_sdk
    from lightning_sdk import Job, Machine, Studio

    config = _check_config()
    patches = _block_network()
    try:
        # Constructors initialize API clients (and may start login). __new__ gives
        # genuine SDK class instances for API inspection without initialization or
        # resource hydration.
        studio = Studio.__new__(Studio)
        job = Job.__new__(Job)
        required = {
            "Studio object": isinstance(studio, Studio),
            "Job object": isinstance(job, Job),
            "Machine.T4": hasattr(Machine, "T4"),
            "Machine.L4": hasattr(Machine, "L4"),
            "Studio.upload_file": callable(getattr(studio, "upload_file", None)),
            "Studio.download_file": callable(getattr(studio, "download_file", None)),
            "Studio.upload_folder": callable(getattr(studio, "upload_folder", None)),
            "Studio.download_folder": callable(getattr(studio, "download_folder", None)),
            "Studio.run": callable(getattr(studio, "run", None)),
            "Studio.stop": callable(getattr(studio, "stop", None)),
            "Job.run": callable(getattr(Job, "run", None)),
            "Job.logs": isinstance(getattr(Job, "logs", None), property),
            "Job.status": isinstance(getattr(Job, "status", None), property),
            "Job.stop": callable(getattr(job, "stop", None)),
            "Job.wait": callable(getattr(job, "wait", None)),
        }
        if not all(required.values()):
            raise RuntimeError(f"Lightning SDK API gate failed: {required}")
        return {
            "status": "SDK_API_SHAPE_VALIDATED",
            "sdk_gate_status": config["sdk_gate_status"],
            "provider_status": config["provider_status"],
            "account_status": config["account_status"],
            "payment_method_account_verified": config["payment_method_account_verified"],
            "credits_status": config["credits_status"],
            "gpu_status": config["gpu_status"],
            "remote_execution_authorized": config["remote_execution_authorized"],
            "sdk_version": importlib.metadata.version("lightning-sdk"),
            "sdk_module_version": getattr(lightning_sdk, "__version__", None),
            "cli_available": bool(shutil.which("lightning")),
            "remote_calls": 0,
            "resources_created": 0,
            "function_executed": False,
            "credentials_used": False,
            "config_status": config["provider_status"],
            "required_apis": required,
        }
    finally:
        _restore_network(patches)


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
