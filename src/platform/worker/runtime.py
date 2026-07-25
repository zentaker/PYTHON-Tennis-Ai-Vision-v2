from __future__ import annotations

import json
import logging
import os
import signal
import stat
import threading
import time
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Callable

from sqlalchemy.orm import Session, sessionmaker

from ..db.repositories.analysis_jobs import get_run
from ..domain.errors import PlatformError
from ..services.analysis_jobs import heartbeat as renew_lease
from ..services.worker_contract import WorkerContractClient
from ..storage.interface import ObjectStorage
from ..storage.keys import bundle_artifact_key, validate_object_key
from .protocol import AnalysisContext, AnalysisProcessor, AnalysisResult, ProcessorOutcome
from .workspace import attempt_workspace, cleanup_workspace, ensure_worker_root

LOGGER = logging.getLogger("tennisai.worker")


class LeaseLost(RuntimeError):
    pass


class PublicationError(RuntimeError):
    def __init__(self, keys: list[str]):
        super().__init__("artifact publication failed")
        self.keys = keys


class WorkerRuntime:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        storage: ObjectStorage,
        *,
        worker_id: str,
        worker_version: str,
        processor_factory: Callable[[], AnalysisProcessor] | None = None,
        worker_root: str | Path = "/tmp/tennisai-worker",
        poll_interval: float = 2.0,
        heartbeat_interval: float = 10.0,
        max_artifact_bytes: int = 2_000_000,
    ) -> None:
        if poll_interval <= 0 or heartbeat_interval <= 0:
            raise ValueError("worker intervals must be positive")
        if heartbeat_interval >= 60:
            raise ValueError("heartbeat interval must be shorter than the lease")
        if max_artifact_bytes <= 0:
            raise ValueError("max artifact size must be positive")
        self.session_factory = session_factory
        self.storage = storage
        self.worker_id = worker_id
        self.worker_version = worker_version
        if processor_factory is None:
            raise ValueError("no analysis processor is configured")
        self.processor_factory = processor_factory
        self.worker_root = ensure_worker_root(worker_root)
        self.poll_interval = poll_interval
        self.heartbeat_interval = heartbeat_interval
        self.max_artifact_bytes = max_artifact_bytes
        self.shutdown_requested = threading.Event()
        self.counters: dict[str, int] = {}
        self.active_stop_event: threading.Event | None = None

    def request_shutdown(self, *_args) -> None:
        self.shutdown_requested.set()
        if self.active_stop_event is not None:
            self.active_stop_event.set()

    def run(self, *, once: bool = False) -> int:
        self._install_signal_handlers()
        while not self.shutdown_requested.is_set():
            processed = self.run_once()
            if once or processed:
                if once:
                    return 0
            if not processed:
                self._event("idle_poll")
                self.shutdown_requested.wait(self.poll_interval)
        return 0

    def run_once(self) -> bool:
        with self.session_factory() as db:
            client = WorkerContractClient(db, self.worker_id, self.worker_version)
            try:
                run = client.claim()
                # ``refresh`` opens a read transaction; release it before a
                # long processor call so cancellation and heartbeat writers
                # are never blocked by the worker's orchestration session.
                db.commit()
            except PlatformError as exc:
                if exc.code == "ANALYSIS_JOB_NOT_AVAILABLE":
                    return False
                LOGGER.info("worker_claim_rejected", extra={"event": "claim_rejected", "code": exc.code})
                return False
            except Exception:
                # Database outages are retried by the outer poll loop without
                # exposing driver messages or connection details.
                self._event("database_unavailable", error_code="WORKER_DATABASE_UNAVAILABLE")
                return False
            run_id = run.id
            self._event("claimed", run_id=str(run.id), attempt=run.attempt)
            cancel_event = threading.Event()
            lease_lost = threading.Event()
            heartbeat_stop = threading.Event()
            cancellation_stop = threading.Event()
            heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                args=(run_id, client.lease_token, heartbeat_stop, lease_lost),
                daemon=True,
                name="analysis-heartbeat",
            )
            workspace = attempt_workspace(self.worker_root, run.id, run.attempt)
            started = time.monotonic()
            published_keys: list[str] = []
            self.active_stop_event = threading.Event()
            heartbeat_thread.start()
            cancellation_thread = threading.Thread(
                target=self._cancellation_loop,
                args=(run_id, cancel_event, cancellation_stop, lease_lost),
                daemon=True,
                name="analysis-cancellation-watch",
            )
            cancellation_thread.start()
            try:
                context = AnalysisContext(
                    run_id=run.id,
                    session_id=run.session_id,
                    input_video_id=run.input_video_id,
                    processing_profile=run.processing_profile,
                    attempt=run.attempt,
                    workspace=workspace,
                    cancellation_requested=cancel_event,
                    shutdown_requested=self.active_stop_event,
                )
                result = self.processor_factory().process(context)
                if lease_lost.is_set() or self.shutdown_requested.is_set():
                    raise LeaseLost()
                # The claim object is deliberately detached from long-running
                # processor work; reload it before every lease-sensitive
                # transition so cancellation written by another session is
                # never hidden by SQLAlchemy's identity map.
                db.expire_all()
                try:
                    outcome = ProcessorOutcome(result.status)
                except (TypeError, ValueError):
                    if not lease_lost.is_set() and not cancel_event.is_set() and not self.shutdown_requested.is_set():
                        client.fail("ANALYSIS_OUTPUT_INVALID", "processor output invalid")
                    self._event("failed", run_id=str(run.id), attempt=run.attempt, error_code="ANALYSIS_OUTPUT_INVALID")
                    return True
                if outcome == ProcessorOutcome.CANCELLED or cancel_event.is_set():
                    client.acknowledge_cancel()
                    self._event("cancelled", run_id=str(run.id), attempt=run.attempt)
                    return True
                if outcome == ProcessorOutcome.FAILED:
                    if result.artifacts or result.error_code not in {"WORKER_FAILED", "ANALYSIS_INPUT_INVALID", "ANALYSIS_OUTPUT_INVALID", "ANALYSIS_CANCELLED"}:
                        client.fail("ANALYSIS_OUTPUT_INVALID", "processor output invalid")
                        return True
                    client.fail(result.error_code or "WORKER_FAILED", "processor failed")
                    self._event("failed", run_id=str(run.id), attempt=run.attempt,
                                error_code=result.error_code or "WORKER_FAILED")
                    return True
                if outcome not in {ProcessorOutcome.COMPLETE, ProcessorOutcome.PARTIAL}:
                    client.fail("ANALYSIS_OUTPUT_INVALID", "processor output invalid")
                    return True
                artifacts, published_keys = self._publish(run.id, run.attempt, workspace, result, cancel_event)
                if lease_lost.is_set() or cancel_event.is_set() or self.shutdown_requested.is_set():
                    raise LeaseLost()
                manifest_key = next(
                    (item["object_key"] for item in artifacts if item["object_key"].endswith("/manifest.json")),
                    artifacts[0]["object_key"],
                )
                if result.result_manifest and result.result_manifest not in {"manifest.json", manifest_key}:
                    raise ValueError("processor returned an unsafe result manifest")
                fingerprint = result.bundle_fingerprint or self._fingerprint(artifacts)
                if outcome == ProcessorOutcome.PARTIAL:
                    client.partial(artifacts, fingerprint, manifest_key)
                    self._event("partial", run_id=str(run.id), attempt=run.attempt)
                else:
                    client.complete(artifacts, fingerprint, manifest_key)
                    self._event("completed", run_id=str(run.id), attempt=run.attempt)
                LOGGER.info(
                    "worker_run_finished",
                    extra={"event": "run_finished", "run_id": str(run.id), "status": result.status,
                           "duration_ms": int((time.monotonic() - started) * 1000)},
                )
                return True
            except LeaseLost:
                self._discard_published(published_keys, run.id, run.attempt)
                self._event("lease_lost")
                LOGGER.info("worker_lease_lost", extra={"event": "lease_lost"})
                return True
            except PlatformError as exc:
                self._discard_published(published_keys, run.id, run.attempt)
                if exc.code == "ANALYSIS_CANCELLATION_INVALID":
                    LOGGER.info("worker_cancel_race", extra={"event": "cancel_race"})
                else:
                    LOGGER.info("worker_transition_rejected", extra={"event": "transition_rejected", "code": exc.code})
                return True
            except PublicationError as exc:
                self._discard_published(exc.keys, run.id, run.attempt)
                LOGGER.info("worker_publication_failed", extra={"event": "publication_failed", "code": "ANALYSIS_OUTPUT_INVALID"})
                return True
            except Exception:
                self._discard_published(published_keys, run.id, run.attempt)
                # Never expose processor exception text, paths, or a traceback.
                try:
                    if not lease_lost.is_set() and not cancel_event.is_set():
                        client.fail("WORKER_FAILED", "processor failed")
                except Exception:
                    pass
                LOGGER.info("worker_run_failed", extra={"event": "run_failed", "code": "WORKER_FAILED"})
                self._event("failed", error_code="WORKER_FAILED")
                return True
            finally:
                heartbeat_stop.set()
                cancellation_stop.set()
                heartbeat_thread.join(timeout=max(1.0, self.heartbeat_interval))
                cancellation_thread.join(timeout=1.0)
                try:
                    cleanup_workspace(self.worker_root, workspace)
                except OSError:
                    LOGGER.info("worker_cleanup_failed", extra={"event": "cleanup_failed"})
                self.active_stop_event = None

    def _heartbeat_loop(self, run_id, token, stop: threading.Event, lost: threading.Event) -> None:
        while not stop.wait(self.heartbeat_interval):
            try:
                with self.session_factory() as db:
                    renew_lease(db, run_id, self.worker_id, token)
            except Exception:
                lost.set()
                return

    def _cancellation_loop(self, run_id, event: threading.Event, stop: threading.Event, lost: threading.Event) -> None:
        # Separate short-lived sessions keep processor code independent of
        # SQLAlchemy state and make cancellation observable during execution.
        while not stop.wait(0.05):
            try:
                with self.session_factory() as db:
                    run = get_run(db, run_id)
                    if run is None or run.cancel_requested_at is not None:
                        event.set()
                        return
            except Exception:
                # A transient database observation failure must not publish an
                # output; the heartbeat/lease remains the authority.
                if lost.is_set():
                    event.set()

    def _publish(self, run_id, attempt: int, workspace: Path, result: AnalysisResult, cancel_event: threading.Event) -> tuple[list[dict], list[str]]:
        try:
            return self._publish_impl(run_id, attempt, workspace, result, cancel_event)
        except PublicationError as exc:
            self._discard_published(exc.keys, run_id, attempt)
            raise

    def _publish_impl(self, run_id, attempt: int, workspace: Path, result: AnalysisResult, cancel_event: threading.Event) -> tuple[list[dict], list[str]]:
        published: list[dict] = []
        keys: list[str] = []
        seen: set[str] = set()
        total = 0
        if len(result.artifacts) > 32:
            raise PublicationError([])
        for descriptor in result.artifacts:
            relative = descriptor.relative_path
            try:
                canonical_relative = validate_object_key(relative)
            except ValueError as exc:
                raise PublicationError(keys) from exc
            if (not relative or canonical_relative != relative or relative.startswith("/") or "\\" in relative
                    or any(ord(char) < 32 or ord(char) == 127 for char in relative)):
                raise PublicationError(keys)
            root = workspace.resolve()
            target = workspace / PurePosixPath(relative)
            resolved = target.resolve(strict=False)
            if root not in resolved.parents or resolved == root:
                raise PublicationError(keys)
            try:
                body = self._read_regular_artifact(workspace, relative)
            except (OSError, ValueError) as exc:
                raise PublicationError(keys) from exc
            if len(body) > self.max_artifact_bytes:
                raise PublicationError(keys)
            total += len(body)
            if total > self.max_artifact_bytes * 4:
                raise PublicationError(keys)
            key = bundle_artifact_key(run_id, f"attempt-{attempt}/{relative}")
            if relative in seen or key in seen:
                raise PublicationError(keys)
            seen.add(relative)
            seen.add(key)
            if cancel_event.is_set() or self.shutdown_requested.is_set():
                raise PublicationError(keys)
            try:
                self.storage.put_bytes(key, body, descriptor.media_type)
            except Exception as exc:
                raise PublicationError(keys) from exc
            keys.append(key)
            published.append({"kind": descriptor.kind.value, "object_key": key, "media_type": descriptor.media_type,
                              "size_bytes": len(body), "sha256": sha256(body).hexdigest(),
                              "schema_version": descriptor.schema_version})
        if not published:
            raise PublicationError(keys)
        return published, keys

    @staticmethod
    def _read_regular_artifact(workspace: Path, relative: str) -> bytes:
        """Read only a non-link regular file, with no-follow semantics."""

        root = workspace.resolve()
        current = root
        parts = PurePosixPath(relative).parts
        for index, part in enumerate(parts):
            current = current / part
            info = os.lstat(current)
            if stat.S_ISLNK(info.st_mode):
                raise ValueError("symlink component")
            if index == len(parts) - 1 and not stat.S_ISREG(info.st_mode):
                raise ValueError("artifact is not a regular file")
        flags = os.O_RDONLY
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(current, flags | nofollow)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("artifact link count or type invalid")
            with os.fdopen(fd, "rb") as handle:
                fd = -1
                return handle.read()
        finally:
            if fd >= 0:
                os.close(fd)

    def _discard_published(self, keys: list[str], run_id=None, attempt: int | None = None) -> None:
        for key in keys:
            if run_id is not None and attempt is not None:
                expected = f"runs/{run_id}/bundle/attempt-{attempt}/"
                if not key.startswith(expected) or validate_object_key(key, expected) != key:
                    continue
            try:
                self.storage.delete_object(key)
            except Exception:
                LOGGER.info("worker_storage_cleanup_failed", extra={"event": "storage_cleanup_failed"})

    def _event(self, name: str, **fields) -> None:
        self.counters[name] = self.counters.get(name, 0) + 1
        LOGGER.info(name, extra={"event": name, "worker_id": self.worker_id, **fields})

    @staticmethod
    def _fingerprint(artifacts: list[dict]) -> str:
        payload = json.dumps(sorted(artifacts, key=lambda item: item["object_key"]), sort_keys=True)
        return sha256(payload.encode()).hexdigest()

    def _install_signal_handlers(self) -> None:
        for name in ("SIGINT", "SIGTERM"):
            try:
                signal.signal(getattr(signal, name), self.request_shutdown)
            except (ValueError, AttributeError):
                pass
