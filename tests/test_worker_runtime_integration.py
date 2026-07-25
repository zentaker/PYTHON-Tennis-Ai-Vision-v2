from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from uuid import uuid4

import pytest

from src.platform.config.settings import PlatformSettings
from src.platform.storage.s3 import S3ObjectStorage

pytestmark = pytest.mark.integration


def _call(base: str, method: str, path: str, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(base + path, data=body, headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _uploaded_session(base: str) -> str:
    status, session = _call(base, "POST", "/api/v1/sessions", {"title": "Stage 2C worker fixture"})
    assert status == 201, session
    body = b"stage2c-worker-input"
    digest = hashlib.sha256(body).hexdigest()
    status, upload = _call(base, "POST", f"/api/v1/sessions/{session['id']}/uploads", {"display_name": "fixture.mp4", "content_type": "video/mp4", "size_bytes": len(body), "sha256": digest})
    assert status == 201, upload
    request = urllib.request.Request(upload["upload_url"], data=body, headers={"Content-Type": "video/mp4"}, method="PUT")
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 200
    status, completed = _call(base, "POST", f"/api/v1/sessions/{session['id']}/uploads/{upload['video_id']}/complete", {"size_bytes": len(body), "content_type": "video/mp4", "sha256": digest})
    assert status == 200, completed
    return session["id"]


def _terminal_run(base: str, session_id: str, profile: str, key: str) -> dict:
    status, queued = _call(base, "POST", "/api/v1/analysis-runs", {"session_id": session_id, "processing_profile": profile, "idempotency_key": key})
    assert status == 202, queued
    run_id = queued["id"]
    for _ in range(80):
        status, current = _call(base, "GET", f"/api/v1/analysis-runs/{run_id}")
        assert status == 200
        if current["status"] in {"COMPLETE", "PARTIAL", "FAILED", "CANCELLED"}:
            return current
        time.sleep(.25)
    raise AssertionError(f"run did not become terminal: {run_id}")


@pytest.mark.skipif(os.getenv("RUN_STAGE2C_WORKER_HTTP_INTEGRATION") != "1", reason="Compose worker is required")
def test_worker_service_processes_http_run_and_persists_minio_artifacts():
    session_base = os.getenv("SESSION_PLATFORM_API_BASE_URL", "http://localhost:8000")
    analysis_base = os.getenv("ANALYSIS_JOB_API_BASE_URL", "http://localhost:8001")
    session_id = _uploaded_session(session_base)
    terminal = _terminal_run(analysis_base, session_id, "STANDARD", f"stage2c-{uuid4()}")
    run_id = terminal["id"]
    assert terminal["status"] == "COMPLETE", terminal
    assert terminal["result_manifest"] == f"runs/{run_id}/bundle/attempt-1/manifest.json"
    storage = S3ObjectStorage(PlatformSettings())
    assert json.loads(storage.get_bytes(terminal["result_manifest"]))["schema_version"] == "stage2c.fixture.v1"
    status, artifacts = _call(session_base, "GET", f"/api/v1/sessions/{session_id}/artifacts")
    assert status == 200 and len(artifacts) >= 2

    partial = _terminal_run(analysis_base, session_id, "FAST", f"stage2c-partial-{uuid4()}")
    failed = _terminal_run(analysis_base, session_id, "TACTICAL", f"stage2c-failed-{uuid4()}")
    assert partial["status"] == "PARTIAL"
    assert failed["status"] == "FAILED" and failed["error_code"] == "ANALYSIS_INPUT_INVALID"

    status, queued = _call(analysis_base, "POST", "/api/v1/analysis-runs", {"session_id": session_id, "processing_profile": "STANDARD", "idempotency_key": f"stage2c-cancel-{uuid4()}"})
    assert status == 202
    status, cancelled = _call(analysis_base, "POST", f"/api/v1/analysis-runs/{queued['id']}/cancel")
    assert status == 200, cancelled
    assert cancelled["status"] == "CANCELLED"
