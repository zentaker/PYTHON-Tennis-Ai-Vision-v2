from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse
from uuid import uuid4

import pytest


pytestmark = pytest.mark.integration


def _call(base: str, method: str, path: str, payload=None, headers=None):
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        base + path,
        data=body,
        headers={"Content-Type": "application/json", **(headers or {})},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, dict(response.headers), json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), json.loads(exc.read())


def _upload(url: str, body: bytes, content_type: str) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": content_type}, method="PUT"
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status, dict(response.headers), response.read()


@pytest.mark.skipif(
    os.getenv("RUN_SESSION_PLATFORM_HTTP_INTEGRATION") != "1",
    reason="set RUN_SESSION_PLATFORM_HTTP_INTEGRATION=1 when API Compose services are ready",
)
def test_complete_session_api_http_lifecycle() -> None:
    base = os.getenv("SESSION_PLATFORM_API_BASE_URL", "http://localhost:8000")
    request_id = f"integration-{uuid4()}"
    status, headers, health = _call(base, "GET", "/healthz", headers={"X-Request-ID": request_id})
    assert status == 200 and health["status"] == "ok"
    assert next(value for key, value in headers.items() if key.lower() == "x-request-id") == request_id

    status, _, created = _call(
        base,
        "POST",
        "/api/v1/sessions",
        {"title": "HTTP integration", "processing_profile": "STANDARD", "surface": "unknown"},
    )
    assert status == 201
    session_id = created["id"]
    assert _call(base, "GET", "/api/v1/sessions")[0] == 200
    assert _call(base, "GET", f"/api/v1/sessions/{session_id}")[1] is not None

    body = b"synthetic-stage2a"
    sha = "A" * 64
    status, _, upload = _call(
        base,
        "POST",
        f"/api/v1/sessions/{session_id}/uploads",
        {
            "display_name": "synthetic.mp4",
            "content_type": "video/mp4",
            "size_bytes": len(body),
            "sha256": sha,
        },
    )
    assert status == 201, upload
    upload_url = upload["upload_url"]
    assert urlparse(upload_url).hostname == "localhost"
    assert urlparse(upload_url).hostname != "minio"

    preflight = urllib.request.Request(
        upload_url,
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type",
        },
        method="OPTIONS",
    )
    with urllib.request.urlopen(preflight, timeout=10) as response:
        assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
        assert "PUT" in response.headers["Access-Control-Allow-Methods"]

    assert _upload(upload_url, body, "video/mp4")[0] == 200
    video_id = upload["video_id"]
    status, _, completed = _call(
        base,
        "POST",
        f"/api/v1/sessions/{session_id}/uploads/{video_id}/complete",
        {"size_bytes": len(body), "content_type": "video/mp4", "sha256": sha.lower()},
    )
    assert status == 200 and completed["integrity_status"] == "STORAGE_VERIFIED"
    assert (
        _call(
            base,
            "POST",
            f"/api/v1/sessions/{session_id}/uploads/{video_id}/complete",
            {"size_bytes": len(body), "content_type": "video/mp4", "sha256": sha.lower()},
        )[0]
        == 200
    )
    session = _call(base, "GET", f"/api/v1/sessions/{session_id}")[2]
    assert session["status"] == "UPLOADED" and session["video"]["id"] == video_id

    status, _, media = _call(base, "GET", f"/api/v1/sessions/{session_id}/media")
    assert status == 200 and urlparse(media["download_url"]).hostname == "localhost"
    with urllib.request.urlopen(media["download_url"], timeout=10) as response:
        assert response.read() == body
        assert response.headers["Content-Type"].split(";", 1)[0] == "video/mp4"
        assert int(response.headers["Content-Length"]) == len(body)

    status, _, error = _call(base, "GET", f"/api/v1/sessions/{uuid4()}")
    assert status == 404 and error["error"]["code"] == "SESSION_NOT_FOUND"
    status, _, error = _call(base, "GET", "/api/v1/sessions?cursor=not-a-cursor")
    assert status == 400 and error["error"]["code"] == "INVALID_CURSOR"
    status, _, error = _call(base, "GET", "/api/v1/sessions?status=not-a-status")
    assert status == 422 and error["error"]["code"] == "VALIDATION_ERROR"
    status, _, error = _call(
        base,
        "POST",
        f"/api/v1/sessions/{session_id}/uploads",
        {"display_name": "bad.txt", "content_type": "video/mp4", "size_bytes": 3},
    )
    assert status == 409 and error["error"]["code"] == "INVALID_SESSION_STATE"


@pytest.mark.skipif(
    os.getenv("RUN_SESSION_PLATFORM_HTTP_INTEGRATION") != "1",
    reason="set RUN_SESSION_PLATFORM_HTTP_INTEGRATION=1 when API Compose services are ready",
)
def test_negative_upload_http_cases() -> None:
    base = os.getenv("SESSION_PLATFORM_API_BASE_URL", "http://localhost:8000")
    _, _, created = _call(base, "POST", "/api/v1/sessions", {"title": "Negative cases"})
    session_id = created["id"]
    status, _, error = _call(
        base,
        "POST",
        f"/api/v1/sessions/{session_id}/uploads",
        {"display_name": "bad.txt", "content_type": "video/mp4", "size_bytes": 3},
    )
    assert status == 422 and error["error"]["code"] == "VIDEO_EXTENSION_MISMATCH"
    status, _, error = _call(
        base,
        "POST",
        f"/api/v1/sessions/{session_id}/uploads",
        {"display_name": "bad.mp4", "content_type": "video/mp4", "size_bytes": 3, "sha256": "bad"},
    )
    assert status == 422 and error["error"]["code"] == "VALIDATION_ERROR"
