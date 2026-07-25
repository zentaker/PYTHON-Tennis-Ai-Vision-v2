from __future__ import annotations

from pathlib import Path
import threading
import time
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.platform.db.base import Base
from src.platform.db.models import SessionRecord, Video
from src.platform.services.analysis_jobs import create_and_queue_run, request_cancellation
from src.platform.storage.interface import ObjectHead
from src.platform.worker.runtime import PublicationError, WorkerRuntime
from src.platform.worker.protocol import AnalysisResult, ProcessorArtifact
from src.platform.domain.enums import ArtifactKind
from src.platform.worker.fixture_processor import ContractFixtureProcessor
from src.product.cli import main as cli_main
from src.platform.worker.workspace import attempt_workspace, cleanup_workspace


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
    engine = create_engine(f"sqlite:///{tmp_path / 'worker.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        session = SessionRecord(title="worker fixture", status="UPLOADED", processing_profile="STANDARD", surface="unknown")
        db.add(session)
        db.flush()
        video = Video(session_id=session.id, role="SOURCE", display_name="fixture.mp4", object_key=f"sessions/{session.id}/source/video", content_type="video/mp4", size_bytes=1, sha256="0" * 64, integrity_status="STORAGE_VERIFIED")
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
    runtime = WorkerRuntime(factory, storage, worker_id="test-worker", worker_version="test", processor_factory=ContractFixtureProcessor, worker_root=workspace_root, poll_interval=.01, heartbeat_interval=1)
    assert runtime.run_once() is True
    with factory() as db:
        result = db.get(type(run), run.id)
        assert result.status == "COMPLETE"
        assert result.result_manifest == f"runs/{run.id}/bundle/attempt-1/manifest.json"
        assert len(result.artifacts) == 2
    assert set(storage.objects) == {f"runs/{run.id}/bundle/attempt-1/manifest.json", f"runs/{run.id}/bundle/attempt-1/metrics.json"}
    assert not list(workspace_root.rglob("*"))


@pytest.mark.parametrize(("profile", "status"), (("FAST", "PARTIAL"), ("TACTICAL", "FAILED")))
def test_worker_fixture_exercises_terminal_paths(fixture_run, tmp_path: Path, profile, status):
    factory, session_id = fixture_run
    with factory() as db:
        run = create_and_queue_run(db, session_id, profile)
    runtime = WorkerRuntime(factory, MemoryStorage(), worker_id="test-worker", worker_version="test", processor_factory=ContractFixtureProcessor, worker_root=tmp_path, poll_interval=.01, heartbeat_interval=1)
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
    runtime = WorkerRuntime(factory, MemoryStorage(), worker_id="test-worker", worker_version="test", processor_factory=ContractFixtureProcessor, worker_root=tmp_path)
    workspace = tmp_path / "attempt"
    workspace.mkdir()
    (workspace / "nested").mkdir()
    (workspace / "nested" / "valid.json").write_text("{}")
    valid = ProcessorArtifact("nested/valid.json", ArtifactKind.MANIFEST, "application/json", "test")
    published, keys = runtime._publish(uuid4(), 2, workspace, AnalysisResult("COMPLETE", (valid,)), threading.Event())
    assert published[0]["object_key"].endswith("/attempt-2/nested/valid.json")
    runtime._discard_published(keys, uuid4(), 2)
    assert keys[0] in runtime.storage.objects
    for relative in ("/etc/passwd", "../secret.json", "", "nested//x.json"):
        with pytest.raises(PublicationError):
            runtime._publish(uuid4(), 1, workspace, AnalysisResult("COMPLETE", (ProcessorArtifact(relative, ArtifactKind.MANIFEST, "application/json", "test"),)), threading.Event())
    outside = tmp_path / "outside.json"
    outside.write_text("secret")
    (workspace / "link.json").symlink_to(outside)
    with pytest.raises(PublicationError):
        runtime._publish(uuid4(), 1, workspace, AnalysisResult("COMPLETE", (ProcessorArtifact("link.json", ArtifactKind.MANIFEST, "application/json", "test"),)), threading.Event())
    with pytest.raises(PublicationError):
        runtime._publish(uuid4(), 1, workspace, AnalysisResult("COMPLETE", (ProcessorArtifact("nested", ArtifactKind.MANIFEST, "application/json", "test"),)), threading.Event())


def test_partial_upload_is_compensated_without_touching_other_attempt(fixture_run, tmp_path: Path):
    factory, _ = fixture_run
    storage = FailOnStorage(1)
    runtime = WorkerRuntime(factory, storage, worker_id="test-worker", worker_version="test", processor_factory=ContractFixtureProcessor, worker_root=tmp_path)
    workspace = tmp_path / "attempt"
    workspace.mkdir()
    (workspace / "one.json").write_text("1")
    (workspace / "two.json").write_text("2")
    result = AnalysisResult("COMPLETE", (
        ProcessorArtifact("one.json", ArtifactKind.MANIFEST, "application/json", "test"),
        ProcessorArtifact("two.json", ArtifactKind.METRICS, "application/json", "test"),
    ))
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

    runtime = WorkerRuntime(factory, MemoryStorage(), worker_id="test-worker", worker_version="test", processor_factory=InvalidProcessor, worker_root=tmp_path)
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
                time.sleep(.01)
            raise AssertionError("cancellation was not observed")

    storage = MemoryStorage()
    runtime = WorkerRuntime(factory, storage, worker_id="test-worker", worker_version="test", processor_factory=SlowProcessor, worker_root=tmp_path, poll_interval=.01, heartbeat_interval=1)
    thread = threading.Thread(target=runtime.run_once)
    thread.start()
    time.sleep(.08)
    with factory() as db:
        request_cancellation(db, run.id)
    thread.join(timeout=3)
    assert not thread.is_alive()
    with factory() as db:
        assert db.get(type(run), run.id).status == "CANCELLED"
    assert storage.objects == {}
