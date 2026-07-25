from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.platform.db.base import Base
from src.platform.db.models import AnalysisRun, SessionRecord, Video
from src.platform.domain.errors import PlatformError
from src.platform.services.analysis_jobs import (
    LEASE_SECONDS,
    claim_next_job,
    complete_run,
    create_and_queue_run,
    fail_run,
    heartbeat,
    reclaim_expired_jobs,
    request_cancellation,
    partial_run,
)
from src.platform.services.worker_contract import WorkerContractClient


@pytest.fixture()
def database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as db:
        yield db


@pytest.fixture()
def uploaded_session(database):
    session = SessionRecord(
        title="Stage 2B synthetic contract",
        status="UPLOADED",
        processing_profile="STANDARD",
        surface="unknown",
    )
    database.add(session)
    database.flush()
    video = Video(
        session_id=session.id,
        role="SOURCE",
        display_name="contract-only.mp4",
        object_key=f"sessions/{session.id}/source/video",
        content_type="video/mp4",
        size_bytes=1,
        sha256="0" * 64,
        integrity_status="STORAGE_VERIFIED",
    )
    database.add(video)
    database.flush()
    session.source_video_id = video.id
    database.commit()
    database.refresh(session)
    return session


def _artifact(run_id, kind="MANIFEST"):
    return {
        "kind": kind,
        "object_key": f"runs/{run_id}/bundle/{kind.lower()}.json",
        "media_type": "application/json",
        "size_bytes": 10,
        "sha256": "a" * 64,
    }


def test_state_machine_and_idempotent_enqueue(database, uploaded_session):
    first = create_and_queue_run(database, uploaded_session.id, "STANDARD")
    second = create_and_queue_run(database, uploaded_session.id, "STANDARD")
    assert first.id == second.id
    assert first.status == "QUEUED"
    assert uploaded_session.status == "QUEUED"
    with pytest.raises(PlatformError) as error:
        create_and_queue_run(database, uploaded_session.id, "FAST")
    assert error.value.code == "SESSION_NOT_READY_FOR_ANALYSIS"


def test_atomic_claim_and_heartbeat(database, uploaded_session):
    run = create_and_queue_run(database, uploaded_session.id, "STANDARD")
    claimed, token = claim_next_job(database, "worker-a", "worker-test")
    assert claimed.id == run.id
    assert claimed.status == "RUNNING"
    assert claimed.attempt == 1
    assert claimed.lease_owner == "worker-a"
    assert claimed.lease_token == token
    assert uploaded_session.status == "PROCESSING"
    before = claimed.lease_expires_at
    renewed = heartbeat(database, run.id, "worker-a", token)
    assert renewed.lease_expires_at > before
    assert renewed.lease_expires_at - renewed.heartbeat_at >= timedelta(seconds=LEASE_SECONDS - 1)
    with pytest.raises(PlatformError) as error:
        heartbeat(database, run.id, "worker-b", token)
    assert error.value.code == "ANALYSIS_LEASE_INVALID"


def test_expired_lease_is_requeued_and_reclaimed(database, uploaded_session):
    create_and_queue_run(database, uploaded_session.id, "STANDARD", max_attempts=2)
    claimed, _ = claim_next_job(database, "worker-a")
    claimed.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    database.commit()
    assert reclaim_expired_jobs(database) == 1
    assert claimed.status == "QUEUED"
    reclaimed, token = claim_next_job(database, "worker-b")
    assert reclaimed.attempt == 2
    assert reclaimed.lease_owner == "worker-b"
    assert token


def test_max_attempts_exhaustion_fails_run_and_session(database, uploaded_session):
    run = create_and_queue_run(database, uploaded_session.id, "STANDARD", max_attempts=1)
    claimed, _ = claim_next_job(database, "worker-a")
    claimed.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    database.commit()
    reclaim_expired_jobs(database)
    assert run.status == "FAILED"
    assert run.error_code == "MAX_ATTEMPTS_EXCEEDED"
    assert uploaded_session.status == "FAILED"
    with pytest.raises(PlatformError) as error:
        claim_next_job(database, "worker-b")
    assert error.value.code == "ANALYSIS_JOB_NOT_AVAILABLE"


def test_artifact_finalization_updates_session(database, uploaded_session):
    run = create_and_queue_run(database, uploaded_session.id, "STANDARD")
    claimed, token = claim_next_job(database, "worker-a")
    completed = complete_run(
        database,
        run.id,
        "worker-a",
        token,
        [_artifact(run.id)],
        bundle_fingerprint="b" * 64,
        result_manifest="manifest.json",
    )
    assert completed.status == "COMPLETE"
    assert completed.terminal_at is not None
    assert completed.lease_token is None
    assert uploaded_session.status == "COMPLETE"
    assert uploaded_session.bundle_fingerprint == "b" * 64
    assert len(completed.artifacts) == 1


def test_invalid_artifact_metadata_is_rejected_without_terminal_state(database, uploaded_session):
    run = create_and_queue_run(database, uploaded_session.id, "STANDARD")
    _, token = claim_next_job(database, "worker-a")
    with pytest.raises(PlatformError) as error:
        complete_run(
            database,
            run.id,
            "worker-a",
            token,
            [{**_artifact(run.id), "object_key": "https://evil.invalid/bundle.json"}],
            bundle_fingerprint="c" * 64,
        )
    assert error.value.code == "ARTIFACT_METADATA_INVALID"
    assert run.status == "RUNNING"


def test_cancellation_is_cooperative(database, uploaded_session):
    run = create_and_queue_run(database, uploaded_session.id, "STANDARD")
    requested = request_cancellation(database, run.id)
    assert requested.status == "CANCELLED"
    assert requested.cancel_requested_at is not None
    other = SessionRecord(
        title="Cancellation worker contract",
        status="UPLOADED",
        processing_profile="STANDARD",
        surface="unknown",
    )
    database.add(other)
    database.flush()
    video = Video(
        session_id=other.id,
        role="SOURCE",
        display_name="cancel.mp4",
        object_key=f"sessions/{other.id}/source/video",
        content_type="video/mp4",
        size_bytes=1,
        sha256="0" * 64,
        integrity_status="STORAGE_VERIFIED",
    )
    database.add(video)
    database.flush()
    other.source_video_id = video.id
    database.commit()
    run2 = create_and_queue_run(database, other.id, "FAST")
    _, token = claim_next_job(database, "worker-a")
    request_cancellation(database, run2.id)
    from src.platform.services.analysis_jobs import acknowledge_cancellation

    cancelled = acknowledge_cancellation(database, run2.id, "worker-a", token)
    assert cancelled.status == "CANCELLED"


def test_failure_message_is_sanitized(database, uploaded_session, caplog):
    run = create_and_queue_run(database, uploaded_session.id, "STANDARD")
    _, token = claim_next_job(database, "worker-a")
    with caplog.at_level(logging.INFO):
        failed = fail_run(
            database,
            run.id,
            "worker-a",
            token,
            "bad code\nwith path https://signed.invalid/?token=secret",
            "line\t/local/private.pem\nAuthorization: Bearer secret",
        )
    assert failed.status == "FAILED"
    assert "\n" not in failed.error_code and "\t" not in failed.error_message
    assert "secret" not in failed.error_message.lower()
    assert "/local" not in failed.error_message
    assert "secret" not in caplog.text.lower()
    assert uploaded_session.status == "FAILED"


def test_partial_worker_contract_and_terminal_heartbeat(database, uploaded_session):
    run = create_and_queue_run(database, uploaded_session.id, "STANDARD")
    worker = WorkerContractClient(database, "worker-contract")
    assert worker.claim().id == run.id
    partial = worker.partial([_artifact(run.id)], "d" * 64, f"runs/{run.id}/bundle/manifest.json")
    assert partial.status == "PARTIAL"
    with pytest.raises(PlatformError) as error:
        worker.heartbeat()
    assert error.value.code == "ANALYSIS_LEASE_INVALID"
    with pytest.raises(PlatformError):
        worker.partial([_artifact(run.id)])
    assert uploaded_session.status == "PARTIAL"


def test_stale_worker_cannot_complete_or_publish_after_reclaim(database, uploaded_session):
    run = create_and_queue_run(database, uploaded_session.id, "STANDARD", max_attempts=2)
    _, old_token = claim_next_job(database, "worker-old")
    run.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    database.commit()
    _, new_token = claim_next_job(database, "worker-new")
    assert new_token != old_token
    with pytest.raises(PlatformError) as error:
        complete_run(database, run.id, "worker-old", old_token, [_artifact(run.id)])
    assert error.value.code in {"ANALYSIS_LEASE_INVALID", "ANALYSIS_LEASE_EXPIRED"}
    with pytest.raises(PlatformError):
        heartbeat(database, run.id, "worker-old", old_token)
    assert run.status == "RUNNING"


def test_artifact_key_matrix_and_cross_run_rejection(database, uploaded_session):
    run = create_and_queue_run(database, uploaded_session.id, "STANDARD")
    _, token = claim_next_job(database, "worker-a")
    invalid_keys = (
        f"runs/{run.id}/bundle/../escape.json",
        f"runs/{run.id}/bundle/%2e%2e/escape.json",
        f"runs/{run.id}/bundle//double.json",
        f"runs/{run.id}/bundle/\\windows.json",
        f"runs/{run.id}/bundle/file.json?signature=x",
        f"runs/{run.id}/bundle/file.json#fragment",
        "file:///tmp/escape.json",
        "https://signed.invalid/file.json",
        "/tmp/local.json",
    )
    for key in invalid_keys:
        with pytest.raises(PlatformError) as error:
            complete_run(
                database,
                run.id,
                "worker-a",
                token,
                [{**_artifact(run.id), "object_key": key}],
            )
        assert error.value.code == "ARTIFACT_METADATA_INVALID"
    from uuid import uuid4

    other_id = uuid4()
    with pytest.raises(PlatformError):
        complete_run(
            database,
            run.id,
            "worker-a",
            token,
            [_artifact(other_id)],
        )


def test_cancellation_blocks_terminal_worker_operations(database, uploaded_session):
    run = create_and_queue_run(database, uploaded_session.id, "STANDARD")
    _, token = claim_next_job(database, "worker-a")
    request_cancellation(database, run.id)
    for operation in (
        lambda: heartbeat(database, run.id, "worker-a", token),
        lambda: complete_run(database, run.id, "worker-a", token, [_artifact(run.id)]),
        lambda: partial_run(database, run.id, "worker-a", token, [_artifact(run.id)]),
        lambda: fail_run(database, run.id, "worker-a", token, "WORKER_FAILED", "ignored"),
    ):
        with pytest.raises(PlatformError) as error:
            operation()
        assert error.value.code == "ANALYSIS_CANCELLATION_INVALID"
    from src.platform.services.analysis_jobs import acknowledge_cancellation

    cancelled = acknowledge_cancellation(database, run.id, "worker-a", token)
    assert cancelled.status == "CANCELLED"
    with pytest.raises(PlatformError) as error:
        request_cancellation(database, run.id)
    assert error.value.code == "ANALYSIS_CANCELLATION_INVALID"


def test_processing_profiles_and_idempotency_key_policy(database, uploaded_session):
    first = create_and_queue_run(
        database, uploaded_session.id, "STANDARD", idempotency_key="request-1"
    )
    assert first.status == "QUEUED"
    with pytest.raises(PlatformError) as error:
        create_and_queue_run(
            database, uploaded_session.id, "STANDARD", max_attempts=2, idempotency_key="request-1"
        )
    assert error.value.code == "IDEMPOTENCY_KEY_REUSED"
    claimed, token = claim_next_job(database, "worker-a")
    fail_run(database, claimed.id, "worker-a", token, "WORKER_FAILED", "ignored")
    fast = create_and_queue_run(
        database, uploaded_session.id, "FAST", idempotency_key="request-fast"
    )
    assert fast.status == "QUEUED"


def test_different_key_does_not_reuse_active_run(database, uploaded_session):
    first = create_and_queue_run(
        database, uploaded_session.id, "STANDARD", idempotency_key="request-1"
    )
    with pytest.raises(PlatformError) as error:
        create_and_queue_run(
            database, uploaded_session.id, "STANDARD", idempotency_key="request-2"
        )
    assert error.value.code == "ACTIVE_ANALYSIS_RUN_EXISTS"
    assert database.query(AnalysisRun).count() == 1
    assert database.get(AnalysisRun, first.id).idempotency_key == "request-1"


def test_unkeyed_terminal_requests_are_not_collapsed(database, uploaded_session):
    run = create_and_queue_run(database, uploaded_session.id, "STANDARD")
    claimed, token = claim_next_job(database, "worker-a")
    fail_run(database, claimed.id, "worker-a", token, "WORKER_FAILED", "ignored")
    rerun = create_and_queue_run(database, uploaded_session.id, "STANDARD")
    assert rerun.id != run.id and rerun.status == "QUEUED"


def test_database_state_constraint_rejects_impossible_status(database, uploaded_session):
    run = create_and_queue_run(database, uploaded_session.id, "STANDARD")
    with pytest.raises(IntegrityError):
        database.execute(
            update(AnalysisRun).where(AnalysisRun.id == run.id).values(status="IMPOSSIBLE")
        )
        database.commit()
    database.rollback()
    assert database.get(AnalysisRun, run.id).status == "QUEUED"
