from __future__ import annotations

import shutil
from pathlib import Path
import threading
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.platform.db.base import Base
from src.platform.db.models import SessionRecord, Video
from src.platform.services.analysis_jobs import (
    claim_next_job,
    create_and_queue_run,
    reclaim_expired_jobs,
    request_cancellation,
)
from src.platform.services.worker_contract import WorkerContractClient
from src.platform.storage.interface import ObjectHead
from src.platform.worker.runtime import PublicationError, WorkerRuntime
from src.platform.worker.protocol import AnalysisResult, ProcessorArtifact
from src.platform.domain.enums import ArtifactKind
from src.platform.worker.fixture_processor import ContractFixtureProcessor
from src.product.cli import main as cli_main
from src.platform.worker.workspace import (
    attempt_workspace,
    capture_workspace_identity,
    cleanup_workspace,
)


class MemoryStorage:
    def __init__(self):
        self.objects = {}

    def put_bytes(self, key, body, content_type):
        self.objects[key] = (body, content_type)

    def head_object(self, key):
        body, content_type = self.objects[key]
        return ObjectHead(key, len(body), content_type, None)

    def object_exists(self, key):
        return key in self.objects

    def delete_object(self, key):
        self.objects.pop(key, None)

    def get_bytes(self, key):
        return self.objects[key][0]

    def bucket_exists(self):
        return True

    def create_presigned_upload(self, key, content_type):
        raise NotImplementedError

    def create_presigned_download(self, key, content_type=None):
        raise NotImplementedError


class FailOnStorage(MemoryStorage):
    def __init__(self, fail_after):
        super().__init__()
        self.fail_after = fail_after

    def put_bytes(self, key, body, content_type):
        if len(self.objects) >= self.fail_after:
            raise OSError("synthetic storage failure")
        super().put_bytes(key, body, content_type)


@pytest.fixture()
def fixture_run(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'worker.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        session = SessionRecord(
            title="worker fixture",
            status="UPLOADED",
            processing_profile="STANDARD",
            surface="unknown",
        )
        db.add(session)
        db.flush()
        video = Video(
            session_id=session.id,
            role="SOURCE",
            display_name="fixture.mp4",
            object_key=f"sessions/{session.id}/source/video",
            content_type="video/mp4",
            size_bytes=1,
            sha256="0" * 64,
            integrity_status="STORAGE_VERIFIED",
        )
        db.add(video)
        db.flush()
        session.source_video_id = video.id
        db.commit()
        yield factory, session.id


def test_worker_fixture_publishes_and_cleans_workspace(fixture_run, tmp_path: Path):
    factory, session_id = fixture_run
    with factory() as db:
        run = create_and_queue_run(db, session_id, "STANDARD")
    storage = MemoryStorage()
    workspace_root = tmp_path / "workspace"
    runtime = WorkerRuntime(
        factory,
        storage,
        worker_id="test-worker",
        worker_version="test",
        processor_factory=ContractFixtureProcessor,
        worker_root=workspace_root,
        poll_interval=0.01,
        heartbeat_interval=1,
    )
    assert runtime.run_once() is True
    with factory() as db:
        result = db.get(type(run), run.id)
        assert result.status == "COMPLETE"
        assert result.result_manifest == f"runs/{run.id}/bundle/attempt-1/manifest.json"
        assert len(result.artifacts) == 2
    assert set(storage.objects) == {
        f"runs/{run.id}/bundle/attempt-1/manifest.json",
        f"runs/{run.id}/bundle/attempt-1/metrics.json",
    }
    assert not list(workspace_root.rglob("*"))


@pytest.mark.parametrize(("profile", "status"), (("FAST", "PARTIAL"), ("TACTICAL", "FAILED")))
def test_worker_fixture_exercises_terminal_paths(fixture_run, tmp_path: Path, profile, status):
    factory, session_id = fixture_run
    with factory() as db:
        run = create_and_queue_run(db, session_id, profile)
    runtime = WorkerRuntime(
        factory,
        MemoryStorage(),
        worker_id="test-worker",
        worker_version="test",
        processor_factory=ContractFixtureProcessor,
        worker_root=tmp_path,
        poll_interval=0.01,
        heartbeat_interval=1,
    )
    runtime.run_once()
    with factory() as db:
        assert db.get(type(run), run.id).status == status


def test_workspace_cleanup_rejects_outside_path(tmp_path: Path):
    workspace = attempt_workspace(tmp_path, uuid4(), 1)
    cleanup_workspace(tmp_path, workspace)
    with pytest.raises(ValueError):
        cleanup_workspace(tmp_path, tmp_path)


def test_cli_requires_explicit_processor_authorization(capsys):
    assert cli_main(["worker", "run", "--once"]) == 2
    assert "not real analysis" in capsys.readouterr().err
    assert cli_main(["worker", "run", "--once", "--processor", "contract-fixture"]) == 2
    assert "disabled by default" in capsys.readouterr().err


def test_artifact_paths_are_confined_and_compensated(fixture_run, tmp_path: Path):
    factory, _ = fixture_run
    runtime = WorkerRuntime(
        factory,
        MemoryStorage(),
        worker_id="test-worker",
        worker_version="test",
        processor_factory=ContractFixtureProcessor,
        worker_root=tmp_path,
    )
    workspace = tmp_path / "attempt"
    workspace.mkdir()
    (workspace / "nested").mkdir()
    (workspace / "nested" / "valid.json").write_text("{}")
    valid = ProcessorArtifact(
        "nested/valid.json", ArtifactKind.MANIFEST, "application/json", "test"
    )
    published, keys = runtime._publish(
        uuid4(), 2, workspace, AnalysisResult("COMPLETE", (valid,)), threading.Event()
    )
    assert published[0]["object_key"].endswith("/attempt-2/nested/valid.json")
    runtime._discard_published(keys, uuid4(), 2)
    assert keys[0] in runtime.storage.objects
    for relative in ("/etc/passwd", "../secret.json", "", "nested//x.json"):
        with pytest.raises(PublicationError):
            runtime._publish(
                uuid4(),
                1,
                workspace,
                AnalysisResult(
                    "COMPLETE",
                    (
                        ProcessorArtifact(
                            relative, ArtifactKind.MANIFEST, "application/json", "test"
                        ),
                    ),
                ),
                threading.Event(),
            )
    outside = tmp_path / "outside.json"
    outside.write_text("secret")
    (workspace / "link.json").symlink_to(outside)
    with pytest.raises(PublicationError):
        runtime._publish(
            uuid4(),
            1,
            workspace,
            AnalysisResult(
                "COMPLETE",
                (
                    ProcessorArtifact(
                        "link.json", ArtifactKind.MANIFEST, "application/json", "test"
                    ),
                ),
            ),
            threading.Event(),
        )
    with pytest.raises(PublicationError):
        runtime._publish(
            uuid4(),
            1,
            workspace,
            AnalysisResult(
                "COMPLETE",
                (ProcessorArtifact("nested", ArtifactKind.MANIFEST, "application/json", "test"),),
            ),
            threading.Event(),
        )


def test_partial_upload_is_compensated_without_touching_other_attempt(fixture_run, tmp_path: Path):
    factory, _ = fixture_run
    storage = FailOnStorage(1)
    runtime = WorkerRuntime(
        factory,
        storage,
        worker_id="test-worker",
        worker_version="test",
        processor_factory=ContractFixtureProcessor,
        worker_root=tmp_path,
    )
    workspace = tmp_path / "attempt"
    workspace.mkdir()
    (workspace / "one.json").write_text("1")
    (workspace / "two.json").write_text("2")
    result = AnalysisResult(
        "COMPLETE",
        (
            ProcessorArtifact("one.json", ArtifactKind.MANIFEST, "application/json", "test"),
            ProcessorArtifact("two.json", ArtifactKind.METRICS, "application/json", "test"),
        ),
    )
    with pytest.raises(PublicationError) as error:
        runtime._publish(uuid4(), 1, workspace, result, threading.Event())
    assert len(error.value.keys) == 1
    runtime._discard_published(error.value.keys, uuid4(), 1)
    preserved = "runs/other/bundle/attempt-2/metrics.json"
    storage.objects[preserved] = (b"other", "application/json")
    runtime._discard_published([preserved], uuid4(), 1)
    assert preserved in storage.objects


@pytest.mark.parametrize("status", ("COMPLET", "SUCCESS", "complete", "", None))
def test_invalid_processor_outcome_fails_closed(fixture_run, tmp_path: Path, status):
    factory, session_id = fixture_run
    with factory() as db:
        run = create_and_queue_run(db, session_id, "STANDARD")

    class InvalidProcessor:
        def process(self, context):
            return AnalysisResult(status)

    runtime = WorkerRuntime(
        factory,
        MemoryStorage(),
        worker_id="test-worker",
        worker_version="test",
        processor_factory=InvalidProcessor,
        worker_root=tmp_path,
    )
    runtime.run_once()
    with factory() as db:
        persisted = db.get(type(run), run.id)
        assert persisted.status == "FAILED"
        assert persisted.error_code == "ANALYSIS_OUTPUT_INVALID"


def test_cancellation_during_processor_is_acknowledged(fixture_run, tmp_path: Path):
    factory, session_id = fixture_run
    with factory() as db:
        run = create_and_queue_run(db, session_id, "STANDARD")

    class SlowProcessor:
        def process(self, context):
            for _ in range(30):
                if context.cancelled():
                    return AnalysisResult("CANCELLED", error_code="ANALYSIS_CANCELLED")
                time.sleep(0.01)
            raise AssertionError("cancellation was not observed")

    storage = MemoryStorage()
    runtime = WorkerRuntime(
        factory,
        storage,
        worker_id="test-worker",
        worker_version="test",
        processor_factory=SlowProcessor,
        worker_root=tmp_path,
        poll_interval=0.01,
        heartbeat_interval=1,
    )
    thread = threading.Thread(target=runtime.run_once)
    thread.start()
    time.sleep(0.08)
    with factory() as db:
        request_cancellation(db, run.id)
    thread.join(timeout=3)
    assert not thread.is_alive()
    with factory() as db:
        assert db.get(type(run), run.id).status == "CANCELLED"
    assert storage.objects == {}


def _path_runtime(fixture_run, tmp_path, *, max_artifact_bytes=2_000_000, storage=None):
    factory, _ = fixture_run
    return WorkerRuntime(
        factory,
        storage or MemoryStorage(),
        worker_id="test-worker",
        worker_version="test",
        processor_factory=ContractFixtureProcessor,
        worker_root=tmp_path,
        max_artifact_bytes=max_artifact_bytes,
    ), tmp_path / "workspace"


def _write_descriptor(workspace: Path, relative: str, body: bytes = b"x") -> ProcessorArtifact:
    target = workspace / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    return ProcessorArtifact(relative, ArtifactKind.MANIFEST, "application/json", "test")


def test_rejects_symlink_to_file_inside_workspace(fixture_run, tmp_path):
    runtime, workspace = _path_runtime(fixture_run, tmp_path)
    workspace.mkdir()
    (workspace / "real.json").write_text("x")
    (workspace / "link.json").symlink_to(workspace / "real.json")
    with pytest.raises(PublicationError):
        runtime._publish(
            uuid4(),
            1,
            workspace,
            AnalysisResult(
                "COMPLETE",
                (
                    ProcessorArtifact(
                        "link.json", ArtifactKind.MANIFEST, "application/json", "test"
                    ),
                ),
            ),
            threading.Event(),
        )


def test_rejects_symlink_to_file_outside_workspace(fixture_run, tmp_path):
    runtime, workspace = _path_runtime(fixture_run, tmp_path)
    workspace.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("x")
    (workspace / "link.json").symlink_to(outside)
    with pytest.raises(PublicationError):
        runtime._publish(
            uuid4(),
            1,
            workspace,
            AnalysisResult(
                "COMPLETE",
                (
                    ProcessorArtifact(
                        "link.json", ArtifactKind.MANIFEST, "application/json", "test"
                    ),
                ),
            ),
            threading.Event(),
        )


def test_rejects_symlinked_parent_directory(fixture_run, tmp_path):
    runtime, workspace = _path_runtime(fixture_run, tmp_path)
    workspace.mkdir()
    real = tmp_path / "real"
    real.mkdir()
    (real / "file.json").write_text("x")
    (workspace / "nested").symlink_to(real, target_is_directory=True)
    with pytest.raises(PublicationError):
        runtime._publish(
            uuid4(),
            1,
            workspace,
            AnalysisResult(
                "COMPLETE",
                (
                    ProcessorArtifact(
                        "nested/file.json", ArtifactKind.MANIFEST, "application/json", "test"
                    ),
                ),
            ),
            threading.Event(),
        )


def test_rejects_hardlink(fixture_run, tmp_path):
    runtime, workspace = _path_runtime(fixture_run, tmp_path)
    workspace.mkdir()
    source = workspace / "source.json"
    source.write_text("x")
    os_link = workspace / "hard.json"
    os_link.hardlink_to(source)
    with pytest.raises(PublicationError):
        runtime._publish(
            uuid4(),
            1,
            workspace,
            AnalysisResult(
                "COMPLETE",
                (
                    ProcessorArtifact(
                        "hard.json", ArtifactKind.MANIFEST, "application/json", "test"
                    ),
                ),
            ),
            threading.Event(),
        )


def test_rejects_duplicate_artifact_descriptor(fixture_run, tmp_path):
    runtime, workspace = _path_runtime(fixture_run, tmp_path)
    workspace.mkdir()
    descriptor = _write_descriptor(workspace, "same.json")
    with pytest.raises(PublicationError):
        runtime._publish(
            uuid4(),
            1,
            workspace,
            AnalysisResult("COMPLETE", (descriptor, descriptor)),
            threading.Event(),
        )


def test_rejects_duplicate_publication_key(fixture_run, tmp_path):
    runtime, workspace = _path_runtime(fixture_run, tmp_path)
    workspace.mkdir()
    descriptor = _write_descriptor(workspace, "same.json")
    with pytest.raises(PublicationError):
        runtime._publish(
            uuid4(),
            1,
            workspace,
            AnalysisResult(
                "COMPLETE",
                (
                    descriptor,
                    ProcessorArtifact(
                        "same.json", ArtifactKind.METRICS, "application/json", "test"
                    ),
                ),
            ),
            threading.Event(),
        )


def test_rejects_single_artifact_size_limit(fixture_run, tmp_path):
    runtime, workspace = _path_runtime(fixture_run, tmp_path, max_artifact_bytes=1)
    workspace.mkdir()
    descriptor = _write_descriptor(workspace, "large.json", b"xx")
    with pytest.raises(PublicationError):
        runtime._publish(
            uuid4(), 1, workspace, AnalysisResult("COMPLETE", (descriptor,)), threading.Event()
        )


def test_rejects_aggregate_artifact_size_limit(fixture_run, tmp_path):
    runtime, workspace = _path_runtime(fixture_run, tmp_path, max_artifact_bytes=1)
    workspace.mkdir()
    descriptors = tuple(_write_descriptor(workspace, f"{index}.json") for index in range(5))
    with pytest.raises(PublicationError):
        runtime._publish(
            uuid4(), 1, workspace, AnalysisResult("COMPLETE", descriptors), threading.Event()
        )


def test_lease_loss_before_publication_fails_closed(fixture_run, tmp_path):
    factory, session_id = fixture_run
    with factory() as db:
        run = create_and_queue_run(db, session_id, "STANDARD")

    class LostRuntime(WorkerRuntime):
        def _heartbeat_loop(self, run_id, token, stop, lost):
            lost.set()

    storage = MemoryStorage()
    runtime = LostRuntime(
        factory,
        storage,
        worker_id="test-worker",
        worker_version="test",
        processor_factory=ContractFixtureProcessor,
        worker_root=tmp_path,
    )
    runtime.run_once()
    with factory() as db:
        assert db.get(type(run), run.id).status == "RUNNING"
    assert storage.objects == {}


def test_publication_after_partial_upload_compensates_current_attempt(fixture_run, tmp_path):
    factory, session_id = fixture_run
    with factory() as db:
        run = create_and_queue_run(db, session_id, "STANDARD")

    class PublishThenLose(WorkerRuntime):
        def _publish(self, *args):
            result = super()._publish(*args)
            self.shutdown_requested.set()
            return result

    storage = MemoryStorage()
    runtime = PublishThenLose(
        factory,
        storage,
        worker_id="test-worker",
        worker_version="test",
        processor_factory=ContractFixtureProcessor,
        worker_root=tmp_path,
    )
    runtime.run_once()
    with factory() as db:
        assert db.get(type(run), run.id).status == "RUNNING"
    assert storage.objects == {}


def test_shutdown_during_processor_stops_without_finalization(fixture_run, tmp_path):
    factory, session_id = fixture_run
    with factory() as db:
        run = create_and_queue_run(db, session_id, "STANDARD")

    class Slow:
        def process(self, context):
            while not context.stopped():
                time.sleep(0.01)
            return AnalysisResult("COMPLETE", ())

    runtime = WorkerRuntime(
        factory,
        MemoryStorage(),
        worker_id="test-worker",
        worker_version="test",
        processor_factory=Slow,
        worker_root=tmp_path,
    )
    thread = threading.Thread(target=runtime.run_once)
    thread.start()
    time.sleep(0.05)
    runtime.request_shutdown()
    thread.join(3)
    with factory() as db:
        assert db.get(type(run), run.id).status == "RUNNING"


def test_shutdown_after_publication_before_finalization_compensates(fixture_run, tmp_path):
    factory, session_id = fixture_run
    with factory() as db:
        create_and_queue_run(db, session_id, "STANDARD")

    class PublishThenShutdown(WorkerRuntime):
        def _publish(self, *args):
            result = super()._publish(*args)
            self.request_shutdown()
            return result

    storage = MemoryStorage()
    runtime = PublishThenShutdown(
        factory,
        storage,
        worker_id="test-worker",
        worker_version="test",
        processor_factory=ContractFixtureProcessor,
        worker_root=tmp_path,
    )
    runtime.run_once()
    assert storage.objects == {}


def test_cancel_and_lease_loss_race_never_publishes_stale_result(fixture_run, tmp_path):
    factory, session_id = fixture_run
    with factory() as db:
        run = create_and_queue_run(db, session_id, "STANDARD")

    class Lost(WorkerRuntime):
        def _heartbeat_loop(self, run_id, token, stop, lost):
            lost.set()

    storage = MemoryStorage()
    runtime = Lost(
        factory,
        storage,
        worker_id="test-worker",
        worker_version="test",
        processor_factory=ContractFixtureProcessor,
        worker_root=tmp_path,
    )
    thread = threading.Thread(target=runtime.run_once)
    thread.start()
    with factory() as db:
        request_cancellation(db, run.id)
    thread.join(3)
    assert storage.objects == {}


def test_attempt_one_cannot_delete_attempt_two_objects(fixture_run, tmp_path):
    factory, session_id = fixture_run
    storage = MemoryStorage()
    with factory() as db:
        run = create_and_queue_run(db, session_id, "STANDARD")
        first, token1 = claim_next_job(db, "worker-a", "test")
        key1 = f"runs/{run.id}/bundle/attempt-1/manifest.json"
        storage.put_bytes(key1, b"old", "application/json")
        first.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        reclaim_expired_jobs(db)
        second, token2 = claim_next_job(db, "worker-b", "test")
        key2 = f"runs/{run.id}/bundle/attempt-2/manifest.json"
        storage.put_bytes(key2, b"new", "application/json")
        client = WorkerContractClient(db, "worker-b", "test")
        client.run_id, client.lease_token = second.id, token2
        client.complete(
            [
                {
                    "kind": "MANIFEST",
                    "object_key": key2,
                    "media_type": "application/json",
                    "size_bytes": 3,
                    "sha256": "a" * 64,
                }
            ],
            "b" * 64,
            key2,
        )
        assert storage.object_exists(key2)
        runtime = WorkerRuntime(
            factory,
            storage,
            worker_id="worker-a",
            worker_version="test",
            processor_factory=ContractFixtureProcessor,
            worker_root=tmp_path,
        )
        runtime._discard_published([key2], run.id, 1)
        assert storage.object_exists(key2)
        assert storage.object_exists(key1)
        assert db.get(type(run), run.id).result_manifest == key2


def test_attempt_one_cannot_finalize_after_attempt_two_claim(fixture_run, tmp_path):
    factory, session_id = fixture_run
    storage = MemoryStorage()
    with factory() as db:
        run = create_and_queue_run(db, session_id, "STANDARD")
        first, token1 = claim_next_job(db, "worker-a", "test")
        first.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        reclaim_expired_jobs(db)
        second, token2 = claim_next_job(db, "worker-b", "test")
        client = WorkerContractClient(db, "worker-b", "test")
        client.run_id, client.lease_token = second.id, token2
        key2 = f"runs/{run.id}/bundle/attempt-2/manifest.json"
        storage.put_bytes(key2, b"new", "application/json")
        client.complete(
            [{"kind": "MANIFEST", "object_key": key2, "media_type": "application/json", "size_bytes": 3, "sha256": "a" * 64}],
            "b" * 64,
            key2,
        )
        stale = WorkerContractClient(db, "worker-a", "test")
        stale.run_id, stale.lease_token = run.id, token1
        with pytest.raises(Exception):
            stale.complete(
                [{"kind": "MANIFEST", "object_key": key2, "media_type": "application/json", "size_bytes": 3, "sha256": "a" * 64}],
                "b" * 64,
                key2,
            )
        assert db.get(type(run), run.id).result_manifest == key2


def test_rejects_symlinked_worker_root(fixture_run, tmp_path):
    factory, _ = fixture_run
    real_root = tmp_path / "real-root"
    real_root.mkdir()
    link_root = tmp_path / "worker-root"
    link_root.symlink_to(real_root, target_is_directory=True)
    with pytest.raises(ValueError):
        WorkerRuntime(
            factory,
            MemoryStorage(),
            worker_id="test-worker",
            worker_version="test",
            processor_factory=ContractFixtureProcessor,
            worker_root=link_root,
        )


def test_rejects_symlinked_run_directory(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    run_id = uuid4()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / str(run_id)).symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        attempt_workspace(root, run_id, 1)


def test_cleanup_never_follows_replaced_workspace(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    run_id = uuid4()
    workspace = attempt_workspace(root, run_id, 1)
    identity = capture_workspace_identity(root, workspace)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("keep")
    workspace.rmdir()
    workspace.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        cleanup_workspace(root, workspace, identity)
    assert sentinel.read_text() == "keep"


def test_rejects_replaced_workspace_symlink(fixture_run, tmp_path):
    factory, session_id = fixture_run
    with factory() as db:
        run = create_and_queue_run(db, session_id, "STANDARD")

    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("keep")

    class ReplaceWorkspace:
        def process(self, context):
            shutil.rmtree(context.workspace)
            context.workspace.symlink_to(outside, target_is_directory=True)
            return AnalysisResult("COMPLETE", ())

    runtime = WorkerRuntime(
        factory,
        MemoryStorage(),
        worker_id="test-worker",
        worker_version="test",
        processor_factory=ReplaceWorkspace,
        worker_root=tmp_path / "worker-root",
    )
    runtime.run_once()
    with factory() as db:
        assert db.get(type(run), run.id).status == "FAILED"
    assert sentinel.read_text() == "keep"


def test_workspace_inode_replacement_fails_closed(fixture_run, tmp_path):
    factory, session_id = fixture_run
    with factory() as db:
        run = create_and_queue_run(db, session_id, "STANDARD")

    class ReplaceDirectory:
        def process(self, context):
            moved = context.workspace.with_name("replaced")
            context.workspace.rename(moved)
            context.workspace.mkdir()
            (context.workspace / "manifest.json").write_text("{}")
            return AnalysisResult("COMPLETE", ())

    storage = MemoryStorage()
    runtime = WorkerRuntime(
        factory,
        storage,
        worker_id="test-worker",
        worker_version="test",
        processor_factory=ReplaceDirectory,
        worker_root=tmp_path / "worker-root",
    )
    runtime.run_once()
    with factory() as db:
        assert db.get(type(run), run.id).status == "FAILED"
    assert storage.objects == {}


def test_oversized_artifact_rejected_before_unbounded_read(fixture_run, tmp_path):
    runtime, workspace = _path_runtime(fixture_run, tmp_path, max_artifact_bytes=1024)
    workspace.mkdir()
    sparse = workspace / "sparse.bin"
    with sparse.open("wb") as handle:
        handle.truncate(1025)
    descriptor = ProcessorArtifact("sparse.bin", ArtifactKind.MANIFEST, "application/octet-stream", "test")
    with pytest.raises(PublicationError):
        runtime._publish(uuid4(), 1, workspace, AnalysisResult("COMPLETE", (descriptor,)), threading.Event())
