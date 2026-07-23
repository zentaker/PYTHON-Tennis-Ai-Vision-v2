from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("RUN_ANALYSIS_JOB_HTTP_INTEGRATION") != "1",
    reason="set RUN_ANALYSIS_JOB_HTTP_INTEGRATION=1 when the analysis API Compose service is ready",
)
def test_analysis_api_runtime_contract_without_media_processing():
    base = os.getenv("ANALYSIS_JOB_API_BASE_URL", "http://localhost:8001")
    with urllib.request.urlopen(base + "/api/v1/analysis/openapi.json", timeout=10) as response:
        document = json.loads(response.read())
    assert "/api/v1/analysis-runs" in document["paths"]
    request = urllib.request.Request(
        base + "/api/v1/analysis-runs",
        data=json.dumps({"session_id": "00000000-0000-0000-0000-000000000000"}).encode(),
        headers={"Content-Type": "application/json", "X-Request-ID": "analysis-contract"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=10)
    except urllib.error.HTTPError as error:
        payload = json.loads(error.read())
        assert error.code == 409
        assert payload["error"]["code"] == "SESSION_NOT_READY_FOR_ANALYSIS"
        assert payload["error"]["request_id"] == "analysis-contract"
    else:
        raise AssertionError("missing session must not enqueue a job")
