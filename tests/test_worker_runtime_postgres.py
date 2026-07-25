from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from src.platform.config.settings import PlatformSettings
from src.platform.db.models import AnalysisRun
from src.platform.db.session import make_session_factory
from src.platform.domain.errors import PlatformError
from src.platform.services.analysis_jobs import claim_next_job, reclaim_expired_jobs
from src.platform.services.worker_contract import WorkerContractClient
from src.platform.storage.s3 import S3ObjectStorage
from tests.test_worker_runtime_integration import _uploaded_session, _call

pytestmark = pytest.mark.integration


@pytest.mark.skipif(os.getenv("RUN_STAGE2C_POSTGRES_INTEGRATION") != "1", reason="PostgreSQL Compose is required")
def test_postgres_stale_attempt_recovery_isolated():
    base = os.getenv("SESSION_PLATFORM_API_BASE_URL", "http://localhost:8000")
    analysis_base = os.getenv("ANALYSIS_JOB_API_BASE_URL", "http://localhost:8001")
    session_id = _uploaded_session(base)
    status, queued = _call(analysis_base, "POST", "/api/v1/analysis-runs", {"session_id": session_id, "processing_profile": "STANDARD", "idempotency_key": "stage2c-stale-postgres"})
    assert status == 202
    run_id = UUID(queued["id"])
    settings = PlatformSettings()
    factory = make_session_factory(settings)
    storage = S3ObjectStorage(settings)
    with factory() as db:
        first, token1 = claim_next_job(db, "stage2c-stale-a", "test")
        assert first.attempt == 1
        first.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        reclaim_expired_jobs(db)
        second, token2 = claim_next_job(db, "stage2c-stale-b", "test")
        assert second.attempt == 2
        old_key = f"runs/{run_id}/bundle/attempt-1/manifest.json"
        new_key = f"runs/{run_id}/bundle/attempt-2/manifest.json"
        storage.put_bytes(old_key, b"attempt-1", "application/json")
        storage.delete_object(old_key)
        storage.put_bytes(new_key, b"attempt-2", "application/json")
        client = WorkerContractClient(db, "stage2c-stale-b", "test")
        client.run_id, client.lease_token = second.id, token2
        client.complete([{"kind": "MANIFEST", "object_key": new_key, "media_type": "application/json", "size_bytes": 9, "sha256": hashlib.sha256(b"attempt-2").hexdigest()}], "b" * 64, new_key)
        stale = WorkerContractClient(db, "stage2c-stale-a", "test")
        stale.run_id, stale.lease_token = run_id, token1
        with pytest.raises(PlatformError):
            stale.complete([{"kind": "MANIFEST", "object_key": new_key, "media_type": "application/json", "size_bytes": 9, "sha256": hashlib.sha256(b"attempt-2").hexdigest()}], "b" * 64, new_key)
        assert storage.object_exists(new_key)
        assert db.get(AnalysisRun, run_id).result_manifest == new_key
        assert not storage.object_exists(old_key)
