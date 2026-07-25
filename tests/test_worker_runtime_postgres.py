from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from src.platform.config.settings import PlatformSettings
from src.platform.db.models import AnalysisRun
from src.platform.db.session import make_session_factory
from src.platform.domain.enums import ArtifactKind
from src.platform.domain.errors import PlatformError
from src.platform.services.analysis_jobs import reclaim_expired_jobs, request_cancellation
from src.platform.storage.s3 import S3ObjectStorage
from src.platform.services.worker_contract import WorkerContractClient
from src.platform.worker.protocol import AnalysisResult, ProcessorArtifact
from src.platform.worker.runtime import WorkerRuntime
from tests.test_worker_runtime_integration import _call, _uploaded_session

pytestmark = pytest.mark.integration


class BarrierStorage:
    """S3 adapter that pauses attempt one after its first successful PUT."""

    def __init__(self, delegate: S3ObjectStorage):
        self.delegate = delegate
        self.first_attempt_one_put = threading.Event()
        self.second_attempt_one_put = threading.Event()
        self.resume_attempt_one = threading.Event()
        self.delete_calls: list[str] = []

    def put_bytes(self, key: str, body: bytes, content_type: str) -> None:
        self.delegate.put_bytes(key, body, content_type)
        if "/attempt-1/" in key and key.endswith("first.json"):
            self.first_attempt_one_put.set()
            if not self.resume_attempt_one.wait(20):
                raise TimeoutError("publication barrier timed out")
        elif "/attempt-1/" in key and key.endswith("second.json"):
            self.second_attempt_one_put.set()

    def delete_object(self, key: str) -> None:
        self.delete_calls.append(key)
        self.delegate.delete_object(key)

    def __getattr__(self, name):
        return getattr(self.delegate, name)


class TwoArtifactProcessor:
    def process(self, context):
        (context.workspace / "first.json").write_text('{"attempt": 1}\n', encoding="utf-8")
        (context.workspace / "second.json").write_text('{"attempt": 1}\n', encoding="utf-8")
        return AnalysisResult(
            "COMPLETE",
            (
                ProcessorArtifact("first.json", ArtifactKind.METRICS, "application/json", "test"),
                ProcessorArtifact("second.json", ArtifactKind.METRICS, "application/json", "test"),
            ),
        )


def _cancel_existing_queue(factory, keep: UUID) -> None:
    with factory() as db:
        pending = db.query(AnalysisRun).filter(AnalysisRun.status == "QUEUED").all()
        for run in pending:
            if run.id != keep:
                request_cancellation(db, run.id)


def _run_real_lease_loss_scenario(tmp_path: Path) -> None:
    base = os.getenv("SESSION_PLATFORM_API_BASE_URL", "http://localhost:8000")
    analysis_base = os.getenv("ANALYSIS_JOB_API_BASE_URL", "http://localhost:8001")
    session_id = _uploaded_session(base)
    status, queued = _call(
        analysis_base,
        "POST",
        "/api/v1/analysis-runs",
        {
            "session_id": session_id,
            "processing_profile": "STANDARD",
            "idempotency_key": f"stage2c-lease-loss-{uuid4()}",
        },
    )
    assert status == 202, queued
    run_id = UUID(queued["id"])
    settings = PlatformSettings()
    factory = make_session_factory(settings)
    storage = BarrierStorage(S3ObjectStorage(settings))
    worker_a = WorkerRuntime(
        factory,
        storage,
        worker_id=f"stage2c-a-{uuid4().hex[:8]}",
        worker_version="test",
        processor_factory=TwoArtifactProcessor,
        worker_root=tmp_path / "worker-a",
        heartbeat_interval=0.1,
        poll_interval=0.01,
    )
    worker_b = WorkerRuntime(
        factory,
        storage,
        worker_id=f"stage2c-b-{uuid4().hex[:8]}",
        worker_version="test",
        processor_factory=TwoArtifactProcessor,
        worker_root=tmp_path / "worker-b",
        heartbeat_interval=0.1,
        poll_interval=0.01,
    )
    _cancel_existing_queue(factory, run_id)
    thread_a = threading.Thread(target=worker_a.run_once)
    thread_a.start()
    assert storage.first_attempt_one_put.wait(15)
    with factory() as db:
        claimed = db.get(AnalysisRun, run_id)
        assert claimed is not None and claimed.attempt == 1
        token1 = claimed.lease_token
        claimed.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        assert reclaim_expired_jobs(db) == 1
    result_b: list[bool] = []
    thread_b = threading.Thread(target=lambda: result_b.append(worker_b.run_once()))
    thread_b.start()
    thread_b.join(15)
    assert not thread_b.is_alive()
    assert result_b == [True], worker_b.counters
    storage.resume_attempt_one.set()
    assert storage.second_attempt_one_put.wait(15)
    thread_a.join(15)
    assert not thread_a.is_alive()

    old_prefix = f"runs/{run_id}/bundle/attempt-1/"
    new_prefix = f"runs/{run_id}/bundle/attempt-2/"
    old_keys = [old_prefix + "first.json", old_prefix + "second.json"]
    new_manifest = new_prefix + "first.json"
    new_second = new_prefix + "second.json"
    assert all(key in storage.delete_calls for key in old_keys)
    assert not any(storage.object_exists(key) for key in old_keys)
    with factory() as db:
        terminal = db.get(AnalysisRun, run_id)
        assert terminal is not None
        if terminal.status != "COMPLETE":
            pytest.fail(
                f"status={terminal.status} error_code={terminal.error_code} "
                f"attempt={terminal.attempt} worker_a={worker_a.counters} worker_b={worker_b.counters}"
            )
        assert terminal.attempt == 2
        assert terminal.result_manifest == new_manifest
        assert all(artifact.object_key.startswith(new_prefix) for artifact in terminal.artifacts)
        assert token1
        stale = WorkerContractClient(db, "stage2c-stale-check", "test")
        stale.run_id, stale.lease_token = run_id, token1
        with pytest.raises(PlatformError):
            stale.complete(
                [{"kind": "MANIFEST", "object_key": new_manifest, "media_type": "application/json", "size_bytes": 14, "sha256": "0" * 64}],
                "0" * 64,
                new_manifest,
            )
    # The stale attempt's production cleanup guard cannot address attempt two.
    worker_a._discard_published([new_manifest, new_second], run_id, 1)
    assert storage.object_exists(new_manifest), storage.delete_calls
    assert storage.object_exists(new_second), storage.delete_calls
    assert storage.object_exists(new_manifest)
    assert storage.object_exists(new_second)


@pytest.mark.skipif(os.getenv("RUN_STAGE2C_POSTGRES_INTEGRATION") != "1", reason="PostgreSQL Compose is required")
def test_real_lease_loss_after_first_publication_compensates_attempt(tmp_path):
    _run_real_lease_loss_scenario(tmp_path)


@pytest.mark.skipif(os.getenv("RUN_STAGE2C_POSTGRES_INTEGRATION") != "1", reason="PostgreSQL Compose is required")
def test_postgres_minio_stale_attempt_cleanup_is_automatic(tmp_path):
    _run_real_lease_loss_scenario(tmp_path)
