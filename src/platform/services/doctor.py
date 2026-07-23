from __future__ import annotations

import sys
from uuid import uuid4

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from ..config.settings import PlatformSettings, get_settings
from ..db.session import make_engine
from ..storage.keys import validate_object_key
from ..storage.s3 import S3ObjectStorage


def _migration_check(engine) -> bool:
    head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    return current == head


def doctor(settings: PlatformSettings | None = None) -> dict[str, object]:
    settings = settings or get_settings()
    checks: dict[str, object] = {
        "config": True,
        "database_select_1": False,
        "alembic_at_head": False,
        "bucket_exists": False,
        "presigned_upload": False,
        "presigned_download": False,
        "public_endpoint": settings.s3_public_endpoint_url,
        "object_put_head_get_delete": False,
        "heavy_imports_absent": not any(
            name in sys.modules for name in ("torch", "torchvision", "ultralytics", "cv2")
        ),
    }
    temporary_key = validate_object_key(f"doctor/{uuid4()}.bin")
    storage: S3ObjectStorage | None = None
    try:
        engine = make_engine(settings)
        with engine.connect() as connection:
            checks["database_select_1"] = connection.execute(text("SELECT 1")).scalar_one() == 1
        checks["alembic_at_head"] = _migration_check(engine)
        engine.dispose()
        storage = S3ObjectStorage(settings)
        checks["bucket_exists"] = storage.bucket_exists()
        upload = storage.create_presigned_upload(temporary_key, "application/octet-stream")
        download = storage.create_presigned_download(temporary_key, "application/octet-stream")
        checks["presigned_upload"] = upload.method == "PUT" and upload.url.startswith(
            settings.s3_public_endpoint_url
        )
        checks["presigned_download"] = download.method == "GET" and download.url.startswith(
            settings.s3_public_endpoint_url
        )
        storage.put_bytes(temporary_key, b"doctor", "application/octet-stream")
        head = storage.head_object(temporary_key)
        checks["object_put_head_get_delete"] = (
            head.size_bytes == 6 and storage.get_bytes(temporary_key) == b"doctor"
        )
    except Exception as exc:
        checks["failure"] = type(exc).__name__
    finally:
        if storage is not None:
            try:
                storage.delete_object(temporary_key)
            except Exception:
                checks["cleanup"] = False
    checks.setdefault("cleanup", True)
    checks["status"] = (
        "ready"
        if all(
            value is True
            for key, value in checks.items()
            if key not in {"public_endpoint", "failure"}
        )
        else "blocked"
    )
    return checks
