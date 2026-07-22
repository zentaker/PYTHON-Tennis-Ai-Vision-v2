from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse
from uuid import uuid4

import pytest


pytestmark = pytest.mark.integration
_OBSERVATIONS: list[dict] = []


def _record(operation: str, status: int, code: str | None = None, **details) -> None:
    observation = {"operation": operation, "status": status}
    if code:
        observation["error_code"] = code
    observation.update(details)
    _OBSERVATIONS.append(observation)
    target = os.getenv("SESSION_PLATFORM_RUNTIME_RESULTS_PATH")
    if target:
        with open(target, "w", encoding="utf-8") as handle:
            json.dump({"observations": _OBSERVATIONS}, handle, indent=2, sort_keys=True)
            handle.write("\n")


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
            result = (response.status, dict(response.headers), json.loads(response.read()))
    except urllib.error.HTTPError as exc:
        result = (exc.code, dict(exc.headers), json.loads(exc.read()))
    body_result = result[2]
    _record(
        f"{method} {path.split('?', 1)[0]}",
        result[0],
        body_result.get("error", {}).get("code") if isinstance(body_result, dict) else None,
    )
    return result


def _upload(url: str, body: bytes, content_type: str) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": content_type}, method="PUT"
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            result = (response.status, dict(response.headers), response.read())
    except urllib.error.HTTPError as exc:
        result = (exc.code, dict(exc.headers), exc.read())
    _record("PUT presigned upload", result[0], host=urlparse(url).hostname)
    return result


def _assert_error(result, status: int, code: str, request_id: str | None = None) -> None:
    assert result[0] == status, result[2]
    assert result[2]["error"]["code"] == code, result[2]
    assert result[2]["error"]["request_id"]
    if request_id:
        assert result[2]["error"]["request_id"] == request_id


def _session(base: str, title: str) -> str:
    status, _, payload = _call(base, "POST", "/api/v1/sessions", {"title": title})
    assert status == 201, payload
    return payload["id"]


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

    session_id = _session(base, "HTTP integration")
    assert _call(base, "GET", "/api/v1/sessions")[0] == 200
    assert _call(base, "GET", f"/api/v1/sessions/{session_id}")[1] is not None

    body = b"synthetic-stage2a"
    sha = hashlib.sha256(body).hexdigest()
    status, _, upload = _call(
        base,
        "POST",
        f"/api/v1/sessions/{session_id}/uploads",
        {"display_name": "synthetic.mp4", "content_type": "video/mp4", "size_bytes": len(body), "sha256": sha.upper()},
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
        cors_headers = {key.lower(): value for key, value in response.headers.items()}
        assert cors_headers["access-control-allow-origin"] == "http://localhost:5173"
        assert "PUT" in cors_headers["access-control-allow-methods"]
        _record(
            "OPTIONS presigned upload",
            response.status,
            cors_origin=cors_headers.get("access-control-allow-origin"),
            allow_methods=cors_headers.get("access-control-allow-methods", "").split(", "),
            allow_headers=cors_headers.get("access-control-allow-headers", "").split(", "),
        )

    assert _upload(upload_url, body, "video/mp4")[0] == 200
    video_id = upload["video_id"]
    status, _, completed = _call(
        base,
        "POST",
        f"/api/v1/sessions/{session_id}/uploads/{video_id}/complete",
        {"size_bytes": len(body), "content_type": "video/mp4", "sha256": sha},
    )
    assert status == 200 and completed["integrity_status"] == "STORAGE_VERIFIED"
    assert _call(
        base,
        "POST",
        f"/api/v1/sessions/{session_id}/uploads/{video_id}/complete",
        {"size_bytes": len(body), "content_type": "video/mp4", "sha256": sha},
    )[0] == 200
    session = _call(base, "GET", f"/api/v1/sessions/{session_id}")[2]
    assert session["status"] == "UPLOADED" and session["video"]["id"] == video_id

    status, _, media = _call(base, "GET", f"/api/v1/sessions/{session_id}/media")
    assert status == 200 and urlparse(media["download_url"]).hostname == "localhost"
    with urllib.request.urlopen(media["download_url"], timeout=10) as response:
        assert response.read() == body
        assert response.headers["Content-Type"].split(";", 1)[0] == "video/mp4"
        assert int(response.headers["Content-Length"]) == len(body)

    _assert_error(_call(base, "GET", f"/api/v1/sessions/{uuid4()}"), 404, "SESSION_NOT_FOUND")
    _assert_error(_call(base, "GET", "/api/v1/sessions?cursor=not-a-cursor"), 400, "INVALID_CURSOR")
    _assert_error(_call(base, "GET", "/api/v1/sessions?status=not-a-status"), 422, "VALIDATION_ERROR")
    _assert_error(
        _call(base, "POST", f"/api/v1/sessions/{session_id}/uploads", {"display_name": "bad.txt", "content_type": "video/mp4", "size_bytes": 3}),
        409,
        "INVALID_SESSION_STATE",
    )


@pytest.mark.skipif(
    os.getenv("RUN_SESSION_PLATFORM_HTTP_INTEGRATION") != "1",
    reason="set RUN_SESSION_PLATFORM_HTTP_INTEGRATION=1 when API Compose services are ready",
)
def test_negative_upload_http_cases() -> None:
    base = os.getenv("SESSION_PLATFORM_API_BASE_URL", "http://localhost:8000")
    session_id = _session(base, "Negative cases")
    request_id = f"negative-{uuid4()}"

    _assert_error(
        _call(base, "POST", f"/api/v1/sessions/{session_id}/uploads", {"display_name": "bad.mp4", "content_type": "video/avi", "size_bytes": 3}, {"X-Request-ID": request_id}),
        422,
        "UNSUPPORTED_VIDEO_CONTENT_TYPE",
        request_id,
    )
    _assert_error(
        _call(base, "POST", f"/api/v1/sessions/{session_id}/uploads", {"display_name": "bad.mp4", "content_type": "video/mp4", "size_bytes": 3, "sha256": "bad"}),
        422,
        "INVALID_SHA256",
    )
    _assert_error(
        _call(base, "POST", f"/api/v1/sessions/{session_id}/uploads", {"display_name": "bad.txt", "content_type": "video/mp4", "size_bytes": 3}),
        422,
        "VIDEO_EXTENSION_MISMATCH",
    )
    _assert_error(
        _call(base, "POST", f"/api/v1/sessions/{session_id}/uploads", {"display_name": "large.mp4", "content_type": "video/mp4", "size_bytes": 2_000_000_001}),
        413,
        "VIDEO_SIZE_EXCEEDED",
    )

    sha_a, sha_b = "a" * 64, "b" * 64
    body = b"sha-mismatch"
    status, _, first = _call(base, "POST", f"/api/v1/sessions/{session_id}/uploads", {"display_name": "sha.mp4", "content_type": "video/mp4", "size_bytes": len(body), "sha256": sha_a})
    assert status == 201
    _assert_error(
        _call(base, "POST", f"/api/v1/sessions/{session_id}/uploads", {"display_name": "duplicate.mp4", "content_type": "video/mp4", "size_bytes": 1}),
        409,
        "SOURCE_VIDEO_ALREADY_EXISTS",
    )
    _upload(first["upload_url"], body, "video/mp4")
    _assert_error(
        _call(base, "POST", f"/api/v1/sessions/{session_id}/uploads/{first['video_id']}/complete", {"size_bytes": len(body), "content_type": "video/mp4", "sha256": sha_b}),
        409,
        "UPLOAD_SHA_MISMATCH",
    )
    _assert_error(
        _call(base, "POST", f"/api/v1/sessions/{session_id}/uploads/{first['video_id']}/complete", {"size_bytes": len(body) + 1, "content_type": "video/mp4", "sha256": sha_a}),
        409,
        "UPLOAD_METADATA_MISMATCH",
    )
    _assert_error(
        _call(base, "POST", f"/api/v1/sessions/{session_id}/uploads/{first['video_id']}/complete", {"size_bytes": len(body), "content_type": "video/quicktime", "sha256": sha_a}),
        409,
        "UPLOAD_METADATA_MISMATCH",
    )

    missing_session = _session(base, "Missing object")
    status, _, missing = _call(base, "POST", f"/api/v1/sessions/{missing_session}/uploads", {"display_name": "missing.mp4", "content_type": "video/mp4", "size_bytes": 4})
    assert status == 201
    _assert_error(
        _call(base, "POST", f"/api/v1/sessions/{missing_session}/uploads/{missing['video_id']}/complete", {"size_bytes": 4, "content_type": "video/mp4"}),
        404,
        "STORAGE_OBJECT_MISSING",
    )

    head_session = _session(base, "HEAD mismatch")
    status, _, head_upload = _call(base, "POST", f"/api/v1/sessions/{head_session}/uploads", {"display_name": "head.mp4", "content_type": "video/mp4", "size_bytes": 10})
    assert status == 201
    _upload(head_upload["upload_url"], b"short", "video/mp4")
    _assert_error(
        _call(base, "POST", f"/api/v1/sessions/{head_session}/uploads/{head_upload['video_id']}/complete", {"size_bytes": 10, "content_type": "video/mp4"}),
        409,
        "STORAGE_OBJECT_MISMATCH",
    )

    other_session = _session(base, "Cross session")
    _assert_error(
        _call(base, "POST", f"/api/v1/sessions/{other_session}/uploads/{first['video_id']}/complete", {"size_bytes": len(body), "content_type": "video/mp4", "sha256": sha_a}),
        404,
        "VIDEO_NOT_FOUND",
    )
    _assert_error(
        _call(base, "GET", f"/api/v1/sessions/{other_session}/media"),
        404,
        "VIDEO_NOT_FOUND",
    )

    page_sessions = [_session(base, f"Page {index}") for index in range(3)]
    status, _, newest = _call(base, "GET", "/api/v1/sessions?limit=2&order=newest")
    assert status == 200 and len(newest["items"]) == 2 and newest["next_cursor"]
    status, _, oldest = _call(base, "GET", "/api/v1/sessions?limit=2&order=oldest")
    assert status == 200 and len(oldest["items"]) == 2 and oldest["next_cursor"]
    status, _, next_page = _call(base, "GET", f"/api/v1/sessions?limit=2&order=newest&cursor={newest['next_cursor']}")
    assert status == 200 and next_page["items"]
    assert set(page_sessions).issubset({item["id"] for item in newest["items"] + next_page["items"]})

    _assert_error(
        _call(base, "POST", f"/api/v1/sessions/{uuid4()}/uploads", {"display_name": "none.mp4", "content_type": "video/mp4", "size_bytes": 1}),
        404,
        "SESSION_NOT_FOUND",
    )
