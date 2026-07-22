from __future__ import annotations

from ..config.settings import get_settings


def doctor() -> dict[str, object]:
    settings = get_settings()
    checks: dict[str, object] = {
        "config": True,
        "database_configured": settings.database_url.startswith("postgresql"),
        "object_storage_configured": bool(settings.s3_bucket and settings.s3_endpoint_url),
        "bucket": settings.s3_bucket,
        "presigned_upload": "not_checked_without_runtime",
        "presigned_download": "not_checked_without_runtime",
        "heavy_imports": "not_loaded",
    }
    checks["status"] = (
        "ready"
        if all(
            value is True
            for key, value in checks.items()
            if key in {"config", "database_configured", "object_storage_configured"}
        )
        else "blocked"
    )
    return checks
