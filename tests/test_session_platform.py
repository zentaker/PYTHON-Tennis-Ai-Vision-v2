from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from src.platform.domain.enums import SessionStatus
from src.platform.domain.transitions import can_transition
from src.platform.storage.interface import ObjectHead, PresignedObject
from src.platform.storage.keys import bundle_artifact_key, source_video_key, validate_object_key

ROOT = Path(__file__).parents[1]


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def create_presigned_upload(self, key, content_type):
        return PresignedObject(
            "http://storage.local/upload",
            "PUT",
            {"Content-Type": content_type},
            datetime.now(timezone.utc),
        )

    def create_presigned_download(self, key, content_type=None):
        return PresignedObject(
            "http://storage.local/download", "GET", {}, datetime.now(timezone.utc)
        )

    def head_object(self, key):
        body, content_type = self.objects[key]
        return ObjectHead(key, len(body), content_type, None)

    def put_bytes(self, key, body, content_type):
        self.objects[key] = (body, content_type)


def test_platform_import_does_not_load_heavy_models() -> None:
    result = subprocess.run(
        [
            "uv",
            "run",
            "--extra",
            "platform",
            "python",
            "-c",
            "import sys; import src.platform; print(any(name in sys.modules for name in ('torch', 'torchvision', 'ultralytics', 'cv2')))",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "False"


def test_domain_transitions_and_object_keys() -> None:
    assert can_transition(SessionStatus.DRAFT, SessionStatus.AWAITING_UPLOAD)
    assert not can_transition(SessionStatus.DRAFT, SessionStatus.COMPLETE)
    session_id, video_id, run_id = uuid4(), uuid4(), uuid4()
    source = source_video_key(session_id, video_id, "match clip.mp4")
    bundle = bundle_artifact_key(run_id, "manifest.json")
    assert source.startswith(f"sessions/{session_id}/source/{video_id}/")
    assert bundle == f"runs/{run_id}/bundle/manifest.json"
    for value in ("../escape", "/absolute", r"a\\b", ""):
        with pytest.raises(ValueError):
            validate_object_key(value)


def test_models_and_upload_lifecycle_with_unit_storage() -> None:
    pytest.importorskip("sqlalchemy")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.platform.config.settings import PlatformSettings
    from src.platform.db.base import Base
    from src.platform.services.sessions import create_session
    from src.platform.services.uploads import complete_upload, initiate_upload

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(engine)() as database:
        settings = PlatformSettings(database_url="sqlite://", max_video_bytes=100)
        storage = FakeStorage()
        record = create_session(database, "Unit session", "STANDARD", "unknown")
        video, _ = initiate_upload(
            database, storage, settings, record, "clip.mp4", "video/mp4", 4, "0" * 64
        )
        storage.put_bytes(video.object_key, b"test", "video/mp4")
        completed = complete_upload(
            database, storage, settings, record, video.id, 4, "video/mp4", "0" * 64
        )
        assert completed.integrity_status == "STORAGE_VERIFIED"
        assert record.status == "UPLOADED"


def test_openapi_snapshot_is_stable() -> None:
    from scripts.export_session_api_openapi import canonical_openapi

    snapshot = json.loads((ROOT / "config/platform/session_api_v1.openapi.json").read_text())
    assert canonical_openapi() == snapshot
    assert "/api/v1/sessions" in snapshot["paths"]
    assert "/api/v1/sessions/{session_id}/uploads/{video_id}/complete" in snapshot["paths"]
    assert "password" not in json.dumps(snapshot).lower()


def test_stage1b_seed_constants_are_metadata_only() -> None:
    from src.platform.services.seed import STAGE1B_FINGERPRINT, STAGE1B_SESSION

    assert STAGE1B_SESSION == "nivel_a2_01"
    assert STAGE1B_FINGERPRINT == "1c0bd683ea349b682be852d02fe7917bea181d8daad42aa97737578d8ceb8009"
