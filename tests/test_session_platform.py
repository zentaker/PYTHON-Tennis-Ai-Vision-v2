from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from src.platform.domain.enums import SessionStatus
from src.platform.domain.errors import PlatformError
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

    def bucket_exists(self):
        return True


class FailingPresignStorage(FakeStorage):
    def create_presigned_upload(self, key, content_type):
        raise OSError("signing unavailable")


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
        assert video.id == record.source_video_id
        assert str(video.id) in video.object_key


def test_presign_failure_rolls_back_without_video_or_state_change() -> None:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from src.platform.config.settings import PlatformSettings
    from src.platform.db.base import Base
    from src.platform.db.models import Video
    from src.platform.services.sessions import create_session
    from src.platform.services.uploads import initiate_upload

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(engine)() as database:
        settings = PlatformSettings(database_url="sqlite://")
        record = create_session(database, "rollback", "STANDARD", "unknown")
        with pytest.raises(PlatformError) as error:
            initiate_upload(
                database,
                FailingPresignStorage(),
                settings,
                record,
                "clip.mp4",
                "video/mp4",
                4,
                None,
            )
        assert error.value.code == "STORAGE_SIGNING_FAILED"
        assert database.scalar(select(Video).where(Video.session_id == record.id)) is None
        database.refresh(record)
        assert record.status == "DRAFT" and record.source_video_id is None


def test_invalid_cursor_is_typed_domain_error() -> None:
    from src.platform.services.sessions import decode_cursor

    with pytest.raises(PlatformError) as error:
        decode_cursor("not-a-cursor")
    assert error.value.status_code == 400
    assert error.value.code == "INVALID_CURSOR"


def test_endpoint_separation_and_public_validation() -> None:
    from pydantic import ValidationError

    from src.platform.config.settings import PlatformSettings

    settings = PlatformSettings(
        s3_internal_endpoint_url="http://minio:9000",
        s3_public_endpoint_url="https://localhost:9443",
    )
    assert settings.s3_internal_endpoint_url != settings.s3_public_endpoint_url
    with pytest.raises(ValidationError):
        PlatformSettings(s3_public_endpoint_url="http://minio:9000")


def test_platform_error_codes_have_documented_openapi_responses() -> None:
    from src.platform.api.app import create_app
    from src.platform.api.errors import ERROR_DEFINITIONS

    openapi = create_app().openapi()
    documented: dict[str, set[int]] = {}
    for path_item in openapi["paths"].values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            for status_code, response in operation.get("responses", {}).items():
                examples = response.get("content", {}).get("application/json", {}).get("examples", {})
                for code in examples:
                    documented.setdefault(code, set()).add(int(status_code))
    for code, (status_code, _, _) in ERROR_DEFINITIONS.items():
        assert code in documented
        assert status_code in documented[code]


def test_public_schemas_use_domain_enums_and_sha_patterns() -> None:
    from src.platform.api.app import create_app

    schemas = create_app().openapi()["components"]["schemas"]
    assert schemas["UploadInitiate"]["properties"]["sha256"]["anyOf"][0]["pattern"] == r"^[0-9a-fA-F]{64}$"
    assert schemas["UploadCompleteResponse"]["properties"]["status"]["$ref"].endswith("SessionStatus")
    assert schemas["MediaResponse"]["properties"]["content_type"]["$ref"].endswith("VideoContentType")
    assert schemas["MediaResponse"]["properties"]["integrity_status"]["$ref"].endswith("IntegrityStatus")
    assert schemas["ArtifactResponse"]["properties"]["kind"]["$ref"].endswith("ArtifactKind")


def test_openapi_snapshot_is_stable() -> None:
    from scripts.export_session_api_openapi import canonical_openapi

    snapshot = json.loads((ROOT / "config/platform/session_api_v1.openapi.json").read_text())
    assert canonical_openapi() == snapshot
    assert "/api/v1/sessions" in snapshot["paths"]
    assert "/api/v1/sessions/{session_id}/uploads/{video_id}/complete" in snapshot["paths"]
    assert "password" not in json.dumps(snapshot).lower()
    assert snapshot["paths"]["/api/v1/sessions"]["post"]["operationId"] == "createSession"
    assert {tag["name"] for tag in snapshot["tags"]} == {
        "Health",
        "Sessions",
        "Uploads",
        "Media",
        "Analysis Runs",
        "Artifacts",
    }


def test_stage1b_seed_constants_are_metadata_only() -> None:
    from src.platform.services.seed import STAGE1B_FINGERPRINT, STAGE1B_SESSION

    assert STAGE1B_SESSION == "nivel_a2_01"
    assert STAGE1B_FINGERPRINT == "1c0bd683ea349b682be852d02fe7917bea181d8daad42aa97737578d8ceb8009"
