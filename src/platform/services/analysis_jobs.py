from __future__ import annotations

import re
from hashlib import sha256
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db.models import AnalysisRun, Artifact, SessionRecord
from ..db.repositories.analysis_jobs import (
    get_active_run,
    get_expired_running,
    get_idempotent_run,
    has_active_run,
    get_next_queued,
    get_run,
    get_session,
    list_runs,
)
from ..domain.analysis_errors import analysis_error
from ..domain.analysis_transitions import require_analysis_transition
from ..domain.enums import AnalysisRunStatus, ArtifactKind, SessionStatus
from ..domain.errors import PlatformError
from ..storage.keys import validate_object_key
from .sessions import transition_session


LEASE_SECONDS = 60
DEFAULT_MAX_ATTEMPTS = 3
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
WORKER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
PUBLIC_FAILURE_CODES = {
    "WORKER_FAILED": "analysis worker failed",
    "ANALYSIS_INPUT_INVALID": "analysis input was invalid",
    "ANALYSIS_OUTPUT_INVALID": "analysis output was invalid",
    "ANALYSIS_CANCELLED": "analysis was cancelled",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _worker(worker_id: str) -> str:
    if not worker_id or not WORKER_RE.fullmatch(worker_id):
        raise analysis_error("WORKER_NOT_AUTHORIZED")
    return worker_id


def _idempotency_key(value: str | None, processing_profile: str) -> str | None:
    del processing_profile
    if value is None:
        return None
    if not IDEMPOTENCY_RE.fullmatch(value):
        raise analysis_error("IDEMPOTENCY_KEY_REUSED")
    return value


def _request_fingerprint(processing_profile: str, max_attempts: int) -> str:
    return sha256(f"{processing_profile}|{max_attempts}".encode()).hexdigest()


def _session_for_run(db: Session, run: AnalysisRun) -> SessionRecord:
    session = get_session(db, run.session_id)
    if session is None:
        raise analysis_error("SESSION_NOT_READY_FOR_ANALYSIS")
    return session


def create_and_queue_run(
    db: Session,
    session_id: UUID,
    processing_profile: str,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    idempotency_key: str | None = None,
) -> AnalysisRun:
    session = get_session(db, session_id)
    if session is None:
        raise analysis_error("SESSION_NOT_READY_FOR_ANALYSIS")
    key = _idempotency_key(idempotency_key, processing_profile)
    fingerprint = _request_fingerprint(processing_profile, max_attempts)
    existing_key = get_idempotent_run(db, session_id, key) if key is not None else None
    if existing_key is not None:
        if existing_key.request_fingerprint != fingerprint:
            raise analysis_error("IDEMPOTENCY_KEY_REUSED")
        return existing_key
    active = get_active_run(db, session_id, processing_profile)
    if active is not None:
        return active
    if has_active_run(db, session_id):
        raise analysis_error("SESSION_NOT_READY_FOR_ANALYSIS")
    if session.status not in {
        SessionStatus.UPLOADED.value,
        SessionStatus.QUEUED.value,
        SessionStatus.PROCESSING.value,
        SessionStatus.COMPLETE.value,
        SessionStatus.PARTIAL.value,
        SessionStatus.FAILED.value,
    }:
        raise analysis_error("SESSION_NOT_READY_FOR_ANALYSIS")
    if session.source_video_id is None:
        raise analysis_error("SESSION_NOT_READY_FOR_ANALYSIS")
    now = _now()
    run = AnalysisRun(
        session_id=session.id,
        input_video_id=session.source_video_id,
        processing_profile=processing_profile,
        idempotency_key=key,
        request_fingerprint=fingerprint,
        status=AnalysisRunStatus.PENDING.value,
        max_attempts=max_attempts,
        created_at=now,
        updated_at=now,
    )
    db.add(run)
    try:
        db.flush()
        require_analysis_transition(AnalysisRunStatus.PENDING, AnalysisRunStatus.QUEUED)
        run.status = AnalysisRunStatus.QUEUED.value
        run.queued_at = now
        session.latest_analysis_run_id = run.id
        if session.status != SessionStatus.QUEUED.value:
            transition_session(db, session, SessionStatus.QUEUED, commit=False)
        db.commit()
        db.refresh(run)
        return run
    except IntegrityError:
        db.rollback()
        active = get_active_run(db, session_id, processing_profile)
        if active is not None:
            return active
        existing_key = get_idempotent_run(db, session_id, key) if key is not None else None
        if existing_key is not None:
            if existing_key.request_fingerprint != fingerprint:
                raise analysis_error("IDEMPOTENCY_KEY_REUSED")
            return existing_key
        raise analysis_error("ACTIVE_ANALYSIS_RUN_EXISTS")


def get_analysis_run(db: Session, run_id: UUID) -> AnalysisRun:
    run = get_run(db, run_id)
    if run is None:
        raise PlatformError(404, "ANALYSIS_RUN_NOT_FOUND", "analysis run not found")
    return run


def list_analysis_runs(db: Session, session_id: UUID) -> list[AnalysisRun]:
    if get_session(db, session_id) is None:
        raise PlatformError(404, "SESSION_NOT_FOUND", "session not found")
    return list_runs(db, session_id)


def _clear_lease(run: AnalysisRun) -> None:
    run.lease_owner = None
    run.lease_token = None
    run.lease_acquired_at = None
    run.lease_expires_at = None
    run.heartbeat_at = None


def _expire_or_requeue(db: Session, run: AnalysisRun, now: datetime) -> bool:
    if (
        run.status != AnalysisRunStatus.RUNNING.value
        or _aware(run.lease_expires_at) is None
        or _aware(run.lease_expires_at) > now
    ):
        return False
    if run.attempt >= run.max_attempts:
        require_analysis_transition(AnalysisRunStatus.RUNNING, AnalysisRunStatus.FAILED)
        run.status = AnalysisRunStatus.FAILED.value
        run.error_code = "MAX_ATTEMPTS_EXCEEDED"
        run.error_message = "analysis attempt limit has been exhausted"
        run.completed_at = now
        run.terminal_at = now
        _clear_lease(run)
        session = _session_for_run(db, run)
        if session.status == SessionStatus.PROCESSING.value:
            transition_session(db, session, SessionStatus.FAILED, commit=False)
        return False
    require_analysis_transition(AnalysisRunStatus.RUNNING, AnalysisRunStatus.QUEUED)
    run.status = AnalysisRunStatus.QUEUED.value
    run.queued_at = now
    _clear_lease(run)
    return True


def reclaim_expired_jobs(db: Session) -> int:
    now = _now()
    changed = 0
    for run in get_expired_running(db, now):
        if _expire_or_requeue(db, run, now):
            changed += 1
    db.commit()
    return changed


def claim_next_job(
    db: Session, worker_id: str, worker_version: str = "contract-harness"
) -> tuple[AnalysisRun, str]:
    owner = _worker(worker_id)
    reclaim_expired_jobs(db)
    run = get_next_queued(db)
    if run is None:
        raise analysis_error("ANALYSIS_JOB_NOT_AVAILABLE")
    now = _now()
    run.attempt += 1
    if run.attempt > run.max_attempts:
        _expire_or_requeue(db, run, now)
        db.commit()
        raise analysis_error("MAX_ATTEMPTS_EXCEEDED")
    require_analysis_transition(AnalysisRunStatus.QUEUED, AnalysisRunStatus.RUNNING)
    session = _session_for_run(db, run)
    if session.status == SessionStatus.QUEUED.value:
        transition_session(db, session, SessionStatus.PROCESSING, commit=False)
    token = uuid4().hex
    run.status = AnalysisRunStatus.RUNNING.value
    run.lease_owner = owner
    run.lease_token = token
    run.lease_acquired_at = now
    run.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
    run.heartbeat_at = now
    run.worker_version = worker_version[:80]
    run.started_at = run.started_at or now
    db.commit()
    db.refresh(run)
    return run, token


def _require_lease(
    db: Session, run_id: UUID, worker_id: str, token: str, *, allow_cancel: bool = False
) -> AnalysisRun:
    run = get_run(db, run_id, for_update=True)
    if run is None:
        raise PlatformError(404, "ANALYSIS_RUN_NOT_FOUND", "analysis run not found")
    if run.status != AnalysisRunStatus.RUNNING.value:
        raise analysis_error("ANALYSIS_LEASE_INVALID")
    if run.cancel_requested_at is not None and not allow_cancel:
        raise analysis_error("ANALYSIS_CANCELLATION_INVALID")
    if run.lease_owner != _worker(worker_id) or not token or run.lease_token != token:
        raise analysis_error("ANALYSIS_LEASE_INVALID")
    if _aware(run.lease_expires_at) is not None and _aware(run.lease_expires_at) <= _now():
        raise analysis_error("ANALYSIS_LEASE_EXPIRED")
    return run


def heartbeat(db: Session, run_id: UUID, worker_id: str, token: str) -> AnalysisRun:
    run = _require_lease(db, run_id, worker_id, token)
    now = _now()
    run.heartbeat_at = now
    run.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
    db.commit()
    db.refresh(run)
    return run


def _safe_manifest(value: str | None, prefix: str) -> str | None:
    if value is None:
        return None
    if len(value) > 2048:
        raise analysis_error("ARTIFACT_METADATA_INVALID")
    candidate = value if value.startswith(prefix) else f"{prefix}{value}"
    try:
        return validate_object_key(candidate, prefix)
    except ValueError as exc:
        raise analysis_error("ARTIFACT_METADATA_INVALID") from exc


def _validate_artifacts(run: AnalysisRun, artifacts: list[dict]) -> list[Artifact]:
    result: list[Artifact] = []
    keys: set[str] = set()
    prefix = f"runs/{run.id}/bundle/"
    for item in artifacts:
        try:
            kind = ArtifactKind(str(item["kind"]))
            key = str(item["object_key"])
            media_type = str(item["media_type"])
            size = int(item["size_bytes"])
            sha256 = str(item["sha256"])
        except (KeyError, TypeError, ValueError) as exc:
            raise analysis_error("ARTIFACT_METADATA_INVALID") from exc
        try:
            canonical_key = validate_object_key(key, prefix)
        except ValueError as exc:
            raise analysis_error("ARTIFACT_METADATA_INVALID") from exc
        if (
            key != canonical_key
            or key in keys
            or size <= 0
            or not SHA256_RE.fullmatch(sha256)
            or not media_type
            or len(media_type) > 100
        ):
            raise analysis_error("ARTIFACT_METADATA_INVALID")
        keys.add(key)
        result.append(
            Artifact(
                analysis_run_id=run.id,
                kind=kind.value,
                object_key=canonical_key,
                media_type=media_type,
                schema_version=item.get("schema_version"),
                size_bytes=size,
                sha256=sha256.lower(),
            )
        )
    return result


def _finalize(
    db: Session,
    run_id: UUID,
    worker_id: str,
    token: str,
    target: AnalysisRunStatus,
    artifacts: list[dict],
    bundle_fingerprint: str | None = None,
    result_manifest: str | None = None,
) -> AnalysisRun:
    run = _require_lease(db, run_id, worker_id, token)
    if run.cancel_requested_at is not None:
        raise analysis_error("ANALYSIS_CANCELLATION_INVALID")
    if target in {AnalysisRunStatus.COMPLETE, AnalysisRunStatus.PARTIAL}:
        if bundle_fingerprint is not None and not SHA256_RE.fullmatch(bundle_fingerprint):
            raise analysis_error("ARTIFACT_METADATA_INVALID")
        run.artifacts.extend(_validate_artifacts(run, artifacts))
        run.result_manifest = _safe_manifest(result_manifest, f"runs/{run.id}/bundle/")
        run.bundle_fingerprint = bundle_fingerprint.lower() if bundle_fingerprint else None
    require_analysis_transition(AnalysisRunStatus.RUNNING, target)
    now = _now()
    run.status = target.value
    run.completed_at = now
    run.terminal_at = now
    _clear_lease(run)
    session = _session_for_run(db, run)
    if session.status == SessionStatus.PROCESSING.value:
        target_session = {
            AnalysisRunStatus.COMPLETE: SessionStatus.COMPLETE,
            AnalysisRunStatus.PARTIAL: SessionStatus.PARTIAL,
        }[target]
        transition_session(db, session, target_session, commit=False)
        session.bundle_fingerprint = run.bundle_fingerprint
        session.analysis_completed_at = now
    db.commit()
    db.refresh(run)
    return run


def complete_run(
    db: Session,
    run_id: UUID,
    worker_id: str,
    token: str,
    artifacts: list[dict],
    bundle_fingerprint: str | None = None,
    result_manifest: str | None = None,
) -> AnalysisRun:
    return _finalize(
        db, run_id, worker_id, token, AnalysisRunStatus.COMPLETE, artifacts, bundle_fingerprint, result_manifest
    )


def partial_run(
    db: Session,
    run_id: UUID,
    worker_id: str,
    token: str,
    artifacts: list[dict],
    bundle_fingerprint: str | None = None,
    result_manifest: str | None = None,
) -> AnalysisRun:
    return _finalize(
        db, run_id, worker_id, token, AnalysisRunStatus.PARTIAL, artifacts, bundle_fingerprint, result_manifest
    )


def fail_run(
    db: Session, run_id: UUID, worker_id: str, token: str, error_code: str, error_message: str
) -> AnalysisRun:
    run = _require_lease(db, run_id, worker_id, token)
    now = _now()
    require_analysis_transition(AnalysisRunStatus.RUNNING, AnalysisRunStatus.FAILED)
    if run.cancel_requested_at is not None:
        raise analysis_error("ANALYSIS_CANCELLATION_INVALID")
    run.status = AnalysisRunStatus.FAILED.value
    run.completed_at = now
    run.terminal_at = now
    normalized_code = re.sub(r"[^A-Z0-9_:-]", "_", error_code.upper())[:80]
    run.error_code = normalized_code if normalized_code in PUBLIC_FAILURE_CODES else "WORKER_FAILED"
    run.error_message = PUBLIC_FAILURE_CODES[run.error_code]
    _clear_lease(run)
    session = _session_for_run(db, run)
    if session.status == SessionStatus.PROCESSING.value:
        transition_session(db, session, SessionStatus.FAILED, commit=False)
        session.error_code = run.error_code
        session.error_message = run.error_message
        session.analysis_completed_at = now
    db.commit()
    db.refresh(run)
    return run


def request_cancellation(db: Session, run_id: UUID) -> AnalysisRun:
    run = get_run(db, run_id, for_update=True)
    if run is None:
        raise PlatformError(404, "ANALYSIS_RUN_NOT_FOUND", "analysis run not found")
    if run.status in {AnalysisRunStatus.PENDING.value, AnalysisRunStatus.QUEUED.value}:
        require_analysis_transition(AnalysisRunStatus(run.status), AnalysisRunStatus.CANCELLED)
        now = _now()
        run.status = AnalysisRunStatus.CANCELLED.value
        run.cancel_requested_at = now
        run.completed_at = now
        run.terminal_at = now
        _clear_lease(run)
        db.commit()
        db.refresh(run)
        return run
    if run.status == AnalysisRunStatus.RUNNING.value:
        run.cancel_requested_at = _now()
        db.commit()
        db.refresh(run)
        return run
    raise analysis_error("ANALYSIS_CANCELLATION_INVALID")


def acknowledge_cancellation(db: Session, run_id: UUID, worker_id: str, token: str) -> AnalysisRun:
    run = _require_lease(db, run_id, worker_id, token, allow_cancel=True)
    if run.cancel_requested_at is None:
        raise analysis_error("ANALYSIS_CANCELLATION_INVALID")
    require_analysis_transition(AnalysisRunStatus.RUNNING, AnalysisRunStatus.CANCELLED)
    now = _now()
    run.status = AnalysisRunStatus.CANCELLED.value
    run.completed_at = now
    run.terminal_at = now
    _clear_lease(run)
    db.commit()
    db.refresh(run)
    return run
