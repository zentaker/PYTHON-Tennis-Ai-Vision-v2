"""Controlled Stage 2B worker protocol harness.

This module only exercises lease and finalization operations. It never imports a
vision model or executes inference.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from .analysis_jobs import (
    acknowledge_cancellation,
    claim_next_job,
    complete_run,
    fail_run,
    heartbeat,
    partial_run,
)


class WorkerContractClient:
    """Internal harness; ``result_manifest`` must be a complete object key.

    Callers should construct manifests with ``bundle_artifact_key(run_id,
    relative_path)`` before invoking ``complete`` or ``partial``. Relative
    paths are intentionally rejected by the service contract.
    """

    def __init__(self, db: Session, worker_id: str, worker_version: str = "contract-harness"):
        self.db = db
        self.worker_id = worker_id
        self.worker_version = worker_version
        self.run_id: UUID | None = None
        self.lease_token: str | None = None

    def claim(self):
        run, token = claim_next_job(self.db, self.worker_id, self.worker_version)
        self.run_id, self.lease_token = run.id, token
        return run

    def heartbeat(self):
        return heartbeat(self.db, self._run_id(), self.worker_id, self._token())

    def complete(
        self,
        artifacts: list[dict],
        bundle_fingerprint: str | None = None,
        result_manifest: str | None = None,
    ):
        return complete_run(
            self.db,
            self._run_id(),
            self.worker_id,
            self._token(),
            artifacts,
            bundle_fingerprint,
            result_manifest,
        )

    def partial(
        self,
        artifacts: list[dict],
        bundle_fingerprint: str | None = None,
        result_manifest: str | None = None,
    ):
        return partial_run(
            self.db,
            self._run_id(),
            self.worker_id,
            self._token(),
            artifacts,
            bundle_fingerprint,
            result_manifest,
        )

    def fail(self, error_code: str, error_message: str):
        return fail_run(
            self.db,
            self._run_id(),
            self.worker_id,
            self._token(),
            error_code,
            error_message,
        )

    def acknowledge_cancel(self):
        return acknowledge_cancellation(
            self.db, self._run_id(), self.worker_id, self._token()
        )

    def _run_id(self) -> UUID:
        if self.run_id is None:
            raise RuntimeError("worker has not claimed a job")
        return self.run_id

    def _token(self) -> str:
        if self.lease_token is None:
            raise RuntimeError("worker has not claimed a lease")
        return self.lease_token
