#!/usr/bin/env python3
"""Offline API-shape gate for the pinned Modal SDK.

The real SDK objects are instantiated but all client entry points are patched to
raise if the SDK attempts authentication or hydration. No Function is spawned.
"""

from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _block_client_calls(modal: Any) -> list[tuple[Any, str, Any]]:
    patches: list[tuple[Any, str, Any]] = []
    client_module = getattr(modal, "client", None)
    for owner in (client_module, modal):
        if owner is None:
            continue
        for name in ("from_env", "connect"):
            original = getattr(owner, name, None)
            if callable(original):
                def blocked(*_args: Any, _name=name, **_kwargs: Any) -> Any:
                    raise AssertionError(f"offline SDK gate attempted cloud call: {_name}")

                setattr(owner, name, blocked)
                patches.append((owner, name, original))
    return patches


def _restore(patches: list[tuple[Any, str, Any]]) -> None:
    for owner, name, original in patches:
        setattr(owner, name, original)


def run() -> dict[str, object]:
    import modal

    patches = _block_client_calls(modal)
    try:
        image = modal.Image.from_dockerfile(
            str(ROOT / "containers/player-perception/Dockerfile"),
            context_dir=ROOT,
        )
        assets = modal.Volume.from_name("tennisai-p1-assets", create_if_missing=True)
        results = modal.Volume.from_name("tennisai-p1-results", create_if_missing=True)
        app = modal.App("tennis-ai-p1-sdk-gate")

        @app.function(
            image=image,
            gpu=["L4", "A10", "T4"],
            single_use_containers=True,
            retries=0,
            timeout=900,
            serialized=True,
        )
        def probe() -> str:
            return "never executed"

        required = {
            "Image.from_dockerfile": hasattr(modal.Image, "from_dockerfile"),
            "Volume.from_name": hasattr(modal.Volume, "from_name"),
            "Volume.batch_upload": hasattr(assets, "batch_upload"),
            "Volume.commit": hasattr(assets, "commit") and hasattr(results, "commit"),
            "Volume.reload": hasattr(results, "reload"),
            "Volume.listdir": hasattr(results, "listdir"),
            "Volume.read_file": hasattr(results, "read_file"),
            "App.function": hasattr(app, "function"),
            "Function.spawn": hasattr(probe, "spawn"),
            "current_input_id": hasattr(modal, "current_input_id"),
        }
        function_call_type = getattr(modal, "FunctionCall", None)
        if function_call_type is None:
            try:
                from modal.functions import FunctionCall as function_call_type
            except ImportError:
                function_call_type = None
        required["FunctionCall.object_id"] = bool(function_call_type and hasattr(function_call_type, "object_id"))
        required["FunctionCall.cancel"] = bool(function_call_type and hasattr(function_call_type, "cancel"))
        if not all(required.values()):
            raise RuntimeError(f"Modal SDK API gate failed: {required}")
        # Construct the batch context only; entering it would be an upload operation.
        batch_context = assets.batch_upload(force=True)
        if batch_context is None:
            raise RuntimeError("Volume.batch_upload(force=True) returned no context")
        return {
            "status": "SDK_API_SHAPE_VALIDATED",
            "sdk_version": importlib.metadata.version("modal"),
            "remote_calls": 0,
            "function_executed": False,
            "required_apis": required,
        }
    finally:
        _restore(patches)


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
