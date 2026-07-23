from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.platform.db.base import Base
from src.platform.db.models import SessionRecord, Video
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
)


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


def test_failure_message_is_sanitized(database, uploaded_session):
    run = create_and_queue_run(database, uploaded_session.id, "STANDARD")
    _, token = claim_next_job(database, "worker-a")
    failed = fail_run(database, run.id, "worker-a", token, "bad code\nwith path", "line\tsecret")
    assert failed.status == "FAILED"
    assert "\n" not in failed.error_code and "\t" not in failed.error_message
    assert uploaded_session.status == "FAILED"
