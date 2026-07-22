from __future__ import annotations

import os
from uuid import uuid4

import pytest


pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("RUN_SESSION_PLATFORM_INTEGRATION") != "1",
    reason="set RUN_SESSION_PLATFORM_INTEGRATION=1 when Compose services are ready",
)
def test_postgres_and_minio_round_trip() -> None:
    from src.platform.config.settings import PlatformSettings
    from src.platform.db.session import make_session_factory
    from src.platform.services.sessions import create_session
    from src.platform.storage.s3 import S3ObjectStorage

    settings = PlatformSettings()
    factory = make_session_factory(settings)
    with factory() as database:
        record = create_session(database, "Stage 2A integration", "STANDARD", "unknown")
        assert record.id

    storage = S3ObjectStorage(settings)
    key = f"integration/{uuid4()}.txt"
    storage.put_bytes(key, b"stage2a", "text/plain")
    head = storage.head_object(key)
    assert head.size_bytes == 7
    assert head.content_type == "text/plain"
    storage.delete_object(key)
