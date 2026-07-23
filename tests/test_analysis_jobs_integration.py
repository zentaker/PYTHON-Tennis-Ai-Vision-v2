from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import UUID

import pytest

from src.platform.config.settings import PlatformSettings
from src.platform.db.models import AnalysisRun
from src.platform.db.session import make_session_factory
from src.platform.domain.errors import PlatformError
from src.platform.services.analysis_jobs import (
    acknowledge_cancellation,
    complete_run,
    fail_run,
    partial_run,
    reclaim_expired_jobs,
    request_cancellation,
)
from src.platform.services.worker_contract import WorkerContractClient

pytestmark = pytest.mark.integration


def _call(base: str, method: str, path: str, payload: dict | None = None):
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        base + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def _upload(url: str, body: bytes) -> int:
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "video/mp4"}, method="PUT"
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.status


def _artifact(run_id, name="manifest.json") -> dict:
    return {
        "kind": "MANIFEST",
        "object_key": f"runs/{run_id}/bundle/{name}",
        "media_type": "application/json",
        "size_bytes": 16,
        "sha256": "a" * 64,
    }


def _compete(factory, run_id):
    def claim(worker_id):
        with factory() as db:
            client = WorkerContractClient(db, worker_id, "compose-contract")
            try:
                run = client.claim()
                return {"worker": worker_id, "run_id": str(run.id), "token": client.lease_token}
            except PlatformError as error:
                return {"worker": worker_id, "error": error.code}

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ("compose-worker-a", "compose-worker-b")))
    claims = [result for result in results if result.get("run_id") == str(run_id)]
    failures = [result for result in results if result.get("error")]
    assert len(claims) == 1, results
    assert len(failures) == 1, results
    assert failures[0]["error"] == "ANALYSIS_JOB_NOT_AVAILABLE"
    return claims[0]


def _new_uploaded_session(base: str, suffix: str) -> str:
    status, session = _call(base, "POST", "/api/v1/sessions", {"title": f"Stage 2B {suffix}"})
    assert status == 201
    session_id = session["id"]
    body = f"stage2b-{suffix}".encode()
    checksum = hashlib.sha256(body).hexdigest()
    status, upload = _call(
        base,
        "POST",
        f"/api/v1/sessions/{session_id}/uploads",
        {
            "display_name": f"{suffix}.mp4",
            "content_type": "video/mp4",
            "size_bytes": len(body),
            "sha256": checksum,
        },
    )
    assert status == 201
    assert _upload(upload["upload_url"], body) == 200
    status, completed = _call(
        base,
        "POST",
        f"/api/v1/sessions/{session_id}/uploads/{upload['video_id']}/complete",
        {"size_bytes": len(body), "content_type": "video/mp4", "sha256": checksum},
    )
    assert status == 200 and completed["integrity_status"] == "STORAGE_VERIFIED"
    return session_id


def _race(factory, operations):
    barrier = Barrier(len(operations))

    def invoke(operation):
        with factory() as db:
            barrier.wait()
            try:
                result = operation(db)
                return result if isinstance(result, (str, int)) else "ok"
            except PlatformError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=len(operations)) as pool:
        return list(pool.map(invoke, operations))


@pytest.mark.skipif(
    os.getenv("RUN_ANALYSIS_JOB_HTTP_INTEGRATION") != "1",
    reason="set RUN_ANALYSIS_JOB_HTTP_INTEGRATION=1 when Compose services are ready",
)
def test_analysis_job_end_to_end_compose_contract():
    session_base = os.getenv("SESSION_PLATFORM_API_BASE_URL", "http://localhost:8000")
    analysis_base = os.getenv("ANALYSIS_JOB_API_BASE_URL", "http://localhost:8001")
    settings = PlatformSettings()
    factory = make_session_factory(settings)

    status, session = _call(session_base, "POST", "/api/v1/sessions", {"title": "Stage 2B contract"})
    assert status == 201
    session_id = session["id"]
    body = b"stage2b-contract-object"
    checksum = hashlib.sha256(body).hexdigest()
    status, upload = _call(
        session_base,
        "POST",
        f"/api/v1/sessions/{session_id}/uploads",
        {
            "display_name": "contract.mp4",
            "content_type": "video/mp4",
            "size_bytes": len(body),
            "sha256": checksum,
        },
    )
    assert status == 201
    assert _upload(upload["upload_url"], body) == 200
    status, completed_video = _call(
        session_base,
        "POST",
        f"/api/v1/sessions/{session_id}/uploads/{upload['video_id']}/complete",
        {"size_bytes": len(body), "content_type": "video/mp4", "sha256": checksum},
    )
    assert status == 200 and completed_video["integrity_status"] == "STORAGE_VERIFIED"

    status, requested = _call(
        analysis_base,
        "POST",
        "/api/v1/analysis-runs",
        {
            "session_id": session_id,
            "processing_profile": "STANDARD",
            "idempotency_key": "compose-complete-1",
        },
    )
    assert status == 202
    run_id = requested["id"]
    assert _call(analysis_base, "GET", f"/api/v1/analysis-runs/{run_id}")[1]["status"] == "QUEUED"
    assert _call(analysis_base, "GET", f"/api/v1/sessions/{session_id}/analysis-runs")[0] == 200
    claim = _compete(factory, run_id)
    with factory() as db:
        worker = WorkerContractClient(db, claim["worker"])
        worker.run_id, worker.lease_token = UUID(run_id), claim["token"]
        assert worker.heartbeat().status == "RUNNING"
        with pytest.raises(PlatformError) as wrong_token:
            complete_run(db, UUID(run_id), claim["worker"], "0" * 32, [_artifact(run_id)])
        assert wrong_token.value.code == "ANALYSIS_LEASE_INVALID"
        assert worker.complete([_artifact(run_id)], "b" * 64, f"runs/{run_id}/bundle/manifest.json").status == "COMPLETE"
    assert _call(analysis_base, "GET", f"/api/v1/analysis-runs/{run_id}")[1]["status"] == "COMPLETE"
    with factory() as db:
        assert db.get(AnalysisRun, UUID(run_id)).status == "COMPLETE"
    status, artifacts = _call(session_base, "GET", f"/api/v1/sessions/{session_id}/artifacts")
    assert status == 200 and len(artifacts) == 1
    # A terminal run can be followed by a distinct profile and idempotency key.
    for profile, key, terminal in (
        ("FAST", "compose-partial-1", "partial"),
        ("TACTICAL", "compose-failed-1", "failed"),
    ):
        status, payload = _call(
            analysis_base,
            "POST",
            "/api/v1/analysis-runs",
            {"session_id": session_id, "processing_profile": profile, "idempotency_key": key},
        )
        assert status == 202
        claim = _compete(factory, payload["id"])
        with factory() as db:
            client = WorkerContractClient(db, claim["worker"])
            client.run_id, client.lease_token = UUID(payload["id"]), claim["token"]
            if terminal == "partial":
                assert client.partial([_artifact(payload["id"], "partial.json")]).status == "PARTIAL"
            else:
                assert client.fail("LEAKED_PATH", "/tmp/private.pem https://signed.invalid/?token=x").status == "FAILED"
        assert _call(analysis_base, "GET", f"/api/v1/analysis-runs/{payload['id']}")[1]["status"] == terminal.upper()

    # Cancellation before claim.
    status, cancelled_request = _call(
        analysis_base,
        "POST",
        "/api/v1/analysis-runs",
        {"session_id": session_id, "processing_profile": "STANDARD", "idempotency_key": "compose-cancel-before"},
    )
    assert status == 202
    status, cancelled = _call(analysis_base, "POST", f"/api/v1/analysis-runs/{cancelled_request['id']}/cancel", {})
    assert status == 200 and cancelled["status"] == "CANCELLED"

    # Cancellation during execution and cooperative acknowledgement.
    status, running_request = _call(
        analysis_base,
        "POST",
        "/api/v1/analysis-runs",
        {"session_id": session_id, "processing_profile": "STANDARD", "idempotency_key": "compose-cancel-running"},
    )
    assert status == 202
    claim = _compete(factory, running_request["id"])
    status, requested_cancel = _call(analysis_base, "POST", f"/api/v1/analysis-runs/{running_request['id']}/cancel", {})
    assert status == 200 and requested_cancel["cancel_requested_at"]
    with factory() as db:
        client = WorkerContractClient(db, claim["worker"])
        client.run_id, client.lease_token = UUID(running_request["id"]), claim["token"]
        assert client.acknowledge_cancel().status == "CANCELLED"

    # Expiry/reclaim invalidates the old worker and rotates the token.
    status, retry_request = _call(
        analysis_base,
        "POST",
        "/api/v1/analysis-runs",
        {"session_id": session_id, "processing_profile": "STANDARD", "idempotency_key": "compose-reclaim"},
    )
    assert status == 202
    old = _compete(factory, retry_request["id"])
    with factory() as db:
        record = db.get(AnalysisRun, UUID(retry_request["id"]))
        record.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    with factory() as db:
        new_worker = WorkerContractClient(db, "compose-reclaimer")
        reclaimed = new_worker.claim()
        assert str(reclaimed.id) == retry_request["id"]
        assert new_worker.lease_token != old["token"]
        stale_worker = WorkerContractClient(db, old["worker"])
        stale_worker.run_id, stale_worker.lease_token = UUID(retry_request["id"]), old["token"]
        with pytest.raises(PlatformError):
            stale_worker.heartbeat()

    public_openapi = json.loads(
        urllib.request.urlopen(analysis_base + "/api/v1/analysis/openapi.json", timeout=15).read()
    )
    operation_ids = {
        operation.get("operationId")
        for path in public_openapi["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict)
    }
    assert not {"claimNextJob", "heartbeatLease", "completeAnalysisRun", "partialAnalysisRun", "failAnalysisRun", "acknowledgeCancellation"} & operation_ids


@pytest.mark.skipif(
    os.getenv("RUN_ANALYSIS_JOB_HTTP_INTEGRATION") != "1",
    reason="set RUN_ANALYSIS_JOB_HTTP_INTEGRATION=1 when Compose services are ready",
)
def test_analysis_job_concurrency_races_compose_contract():
    session_base = os.getenv("SESSION_PLATFORM_API_BASE_URL", "http://localhost:8000")
    analysis_base = os.getenv("ANALYSIS_JOB_API_BASE_URL", "http://localhost:8001")
    factory = make_session_factory(PlatformSettings())

    # Two reclaimers race on one expired lease; exactly one transaction requeues it.
    session_id = _new_uploaded_session(session_base, "race-reclaim")
    status, requested = _call(
        analysis_base,
        "POST",
        "/api/v1/analysis-runs",
        {"session_id": session_id, "processing_profile": "STANDARD", "idempotency_key": "race-reclaim"},
    )
    assert status == 202
    run_id = UUID(requested["id"])
    with factory() as db:
        worker = WorkerContractClient(db, "race-old")
        assert worker.claim().id == run_id
        token = worker.lease_token
        record = db.get(AnalysisRun, run_id)
        record.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    reclaim_results = _race(factory, (reclaim_expired_jobs, reclaim_expired_jobs))
    assert reclaim_results.count(1) == 1
    with factory() as db:
        record = db.get(AnalysisRun, run_id)
        assert record.status == "QUEUED" and record.lease_token is None
        stale = WorkerContractClient(db, "race-old")
        stale.run_id, stale.lease_token = run_id, token
        with pytest.raises(PlatformError):
            stale.complete([_artifact(run_id)])
        assert request_cancellation(db, run_id).status == "CANCELLED"

    # Heartbeat and reclaim race with a live lease: heartbeat wins and reclaim is a no-op.
    session_id = _new_uploaded_session(session_base, "race-heartbeat")
    status, requested = _call(
        analysis_base,
        "POST",
        "/api/v1/analysis-runs",
        {"session_id": session_id, "processing_profile": "STANDARD", "idempotency_key": "race-heartbeat"},
    )
    assert status == 202
    run_id = UUID(requested["id"])
    with factory() as db:
        worker = WorkerContractClient(db, "heartbeat-winner")
        assert worker.claim().id == run_id
        token = worker.lease_token
        record = db.get(AnalysisRun, run_id)
        record.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=30)
        db.commit()

    def heartbeat_operation(db):
        client = WorkerContractClient(db, "heartbeat-winner")
        client.run_id, client.lease_token = run_id, token
        client.heartbeat()
        return "heartbeat"

    def reclaim_operation(db):
        return reclaim_expired_jobs(db)

    race_results = _race(factory, (heartbeat_operation, reclaim_operation))
    assert "heartbeat" in race_results
    with factory() as db:
        record = db.get(AnalysisRun, run_id)
        assert record.status == "RUNNING"

    # With an already expired lease the reclaim transaction wins over heartbeat.
    session_id = _new_uploaded_session(session_base, "race-expired-heartbeat")
    status, requested = _call(
        analysis_base,
        "POST",
        "/api/v1/analysis-runs",
        {"session_id": session_id, "processing_profile": "STANDARD", "idempotency_key": "race-expired-heartbeat"},
    )
    assert status == 202
    run_id = UUID(requested["id"])
    with factory() as db:
        worker = WorkerContractClient(db, "expired-heartbeat")
        assert worker.claim().id == run_id
        token = worker.lease_token
        record = db.get(AnalysisRun, run_id)
        record.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    def expired_heartbeat(db):
        client = WorkerContractClient(db, "expired-heartbeat")
        client.run_id, client.lease_token = run_id, token
        client.heartbeat()
        return "heartbeat"

    expired_results = _race(factory, (expired_heartbeat, reclaim_expired_jobs))
    assert 1 in expired_results and "heartbeat" not in expired_results

    # Cancellation linearizes against each terminal worker operation.
    for profile, key, terminal in (
        ("FAST", "race-cancel-complete", "complete"),
        ("TACTICAL", "race-cancel-partial", "partial"),
        ("STANDARD", "race-cancel-fail", "fail"),
    ):
        session_id = _new_uploaded_session(session_base, key)
        status, requested = _call(
            analysis_base,
            "POST",
            "/api/v1/analysis-runs",
            {"session_id": session_id, "processing_profile": profile, "idempotency_key": key},
        )
        assert status == 202
        run_id = UUID(requested["id"])
        with factory() as db:
            worker = WorkerContractClient(db, f"{key}-worker")
            assert worker.claim().id == run_id
            token = worker.lease_token

        def cancel_operation(db):
            request_cancellation(db, run_id)
            return "cancel"

        def terminal_operation(db):
            if terminal == "complete":
                complete_run(db, run_id, f"{key}-worker", token, [_artifact(run_id)])
            elif terminal == "partial":
                partial_run(db, run_id, f"{key}-worker", token, [_artifact(run_id)])
            else:
                fail_run(db, run_id, f"{key}-worker", token, "WORKER_FAILED", "secret /tmp/key")
            return terminal

        results = _race(factory, (cancel_operation, terminal_operation))
        assert "cancel" in results or terminal in results
        with factory() as db:
            record = db.get(AnalysisRun, run_id)
            assert record.status in {"RUNNING", "COMPLETE", "PARTIAL", "FAILED"}
            if record.status == "RUNNING":
                assert record.cancel_requested_at is not None
                acknowledged = acknowledge_cancellation(db, run_id, f"{key}-worker", token)
                assert acknowledged.status == "CANCELLED"

    # Cancellation and heartbeat linearize the same way: a cancellation marker
    # prevents renewal, then acknowledgement owns the terminal transition.
    session_id = _new_uploaded_session(session_base, "race-cancel-heartbeat")
    status, requested = _call(
        analysis_base,
        "POST",
        "/api/v1/analysis-runs",
        {"session_id": session_id, "processing_profile": "STANDARD", "idempotency_key": "race-cancel-heartbeat"},
    )
    assert status == 202
    run_id = UUID(requested["id"])
    with factory() as db:
        worker = WorkerContractClient(db, "cancel-heartbeat")
        assert worker.claim().id == run_id
        token = worker.lease_token

    def cancel_heartbeat(db):
        request_cancellation(db, run_id)
        return "cancel"

    def heartbeat_after_cancel_race(db):
        client = WorkerContractClient(db, "cancel-heartbeat")
        client.run_id, client.lease_token = run_id, token
        client.heartbeat()
        return "heartbeat"

    heartbeat_results = _race(factory, (cancel_heartbeat, heartbeat_after_cancel_race))
    assert "cancel" in heartbeat_results
    with factory() as db:
        record = db.get(AnalysisRun, run_id)
        if record.status == "RUNNING":
            assert record.cancel_requested_at is not None
            assert acknowledge_cancellation(db, run_id, "cancel-heartbeat", token).status == "CANCELLED"

    # Acknowledge and complete race: acknowledgement owns the already-requested
    # cancellation, so completion cannot publish after that point.
    session_id = _new_uploaded_session(session_base, "race-ack-complete")
    status, requested = _call(
        analysis_base,
        "POST",
        "/api/v1/analysis-runs",
        {"session_id": session_id, "processing_profile": "STANDARD", "idempotency_key": "race-ack-complete"},
    )
    assert status == 202
    run_id = UUID(requested["id"])
    with factory() as db:
        worker = WorkerContractClient(db, "ack-complete")
        assert worker.claim().id == run_id
        token = worker.lease_token
        request_cancellation(db, run_id)

    def acknowledge_operation(db):
        return acknowledge_cancellation(db, run_id, "ack-complete", token).status

    def complete_after_ack(db):
        complete_run(db, run_id, "ack-complete", token, [_artifact(run_id)])
        return "complete"

    ack_results = _race(factory, (acknowledge_operation, complete_after_ack))
    assert "CANCELLED" in ack_results
    with factory() as db:
        assert db.get(AnalysisRun, run_id).status == "CANCELLED"

    # A cancellation after a committed terminal result cannot alter it.
    session_id = _new_uploaded_session(session_base, "cancel-after-terminal")
    status, requested = _call(
        analysis_base,
        "POST",
        "/api/v1/analysis-runs",
        {"session_id": session_id, "processing_profile": "STANDARD", "idempotency_key": "cancel-after-terminal"},
    )
    assert status == 202
    terminal_id = UUID(requested["id"])
    with factory() as db:
        worker = WorkerContractClient(db, "terminal-worker")
        assert worker.claim().id == terminal_id
        worker.complete([_artifact(terminal_id)])
    status, cancelled = _call(analysis_base, "POST", f"/api/v1/analysis-runs/{terminal_id}/cancel", {})
    assert status == 409 and cancelled["error"]["code"] == "ANALYSIS_CANCELLATION_INVALID"
